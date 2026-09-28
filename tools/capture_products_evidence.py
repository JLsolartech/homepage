"""Capture Products page screenshots and selection/lightbox interaction recordings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright


def capture(browser, base_url: str, out: Path, label: str, viewport: dict[str, int], mobile=False):
    video_dir = out / f"video-{label}"
    options = {
        "viewport": viewport,
        "record_video_dir": str(video_dir),
        "record_video_size": viewport,
    }
    if mobile:
        options.update(is_mobile=True, has_touch=True, device_scale_factor=2)

    context = browser.new_context(**options)
    page = context.new_page()
    page.goto(f"{base_url}/products/", wait_until="networkidle")
    initial_images = page.evaluate(
        """() => performance.getEntriesByType('resource')
          .filter((entry) => entry.name.includes('/assets/optimized/'))
          .map((entry) => ({file: entry.name.split('/').pop(), encoded_bytes: entry.encodedBodySize,
                            transferred_bytes: entry.transferSize}))"""
    )
    page.screenshot(path=str(out / f"products-{label}-full.png"), full_page=True)

    page.locator("[data-product-sample]").nth(1).click()
    page.wait_for_timeout(250)
    page.screenshot(path=str(out / f"products-{label}-silver-sample.png"), full_page=True)

    page.locator("[data-product-lightbox-link]").click()
    page.wait_for_function(
        "() => { const img = document.querySelector('[data-product-lightbox-image]'); return img.complete && img.naturalWidth > 0 && /R5_L6202-(1600|2400)\\.(avif|webp)$/.test(img.currentSrc); }",
        timeout=15000)
    page.screenshot(path=str(out / f"products-{label}-lightbox.png"))
    detail_images = page.evaluate(
        """() => performance.getEntriesByType('resource')
          .filter((entry) => /R5_L6202-(1600|2400)\\.(avif|webp)$/.test(entry.name))
          .map((entry) => ({file: entry.name.split('/').pop(), encoded_bytes: entry.encodedBodySize,
                            transferred_bytes: entry.transferSize}))"""
    )
    page.keyboard.press("Escape")

    if mobile:
        for _ in range(10):
            page.evaluate("window.scrollBy(0, Math.round(innerHeight * 0.55))")
            page.wait_for_timeout(90)
    else:
        for _ in range(10):
            page.mouse.wheel(0, 420)
            page.wait_for_timeout(90)

    video_path = page.video.path()
    context.close()
    target = out / f"products-{label}-interaction.webm"
    Path(video_path).replace(target)
    video_dir.rmdir()
    return {
        "recording": target.name,
        "screenshots": [f"products-{label}-full.png", f"products-{label}-silver-sample.png",
                        f"products-{label}-lightbox.png"],
        "initial_optimized_assets": initial_images,
        "on_demand_detail_assets": detail_images,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:4173")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        desktop = capture(browser, args.base_url, args.out, "desktop-1440",
                          {"width": 1440, "height": 900})
        mobile = capture(browser, args.base_url, args.out, "mobile-390",
                         {"width": 390, "height": 844}, mobile=True)
        browser.close()

    manifest = {
        "preview": args.base_url,
        "browser": "Playwright Chromium",
        "viewports": {"desktop": "1440x900", "mobile": "390x844 (emulated)"},
        "desktop": desktop,
        "mobile": mobile,
        "limitations": ["Mobile is emulated, not a physical device."],
    }
    (args.out / "products-evidence.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
