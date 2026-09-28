"""Capture matched Products A/B screenshots and real-scroll recordings."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from playwright.sync_api import sync_playwright


def reveal_page(page) -> None:
    page.evaluate("document.documentElement.style.scrollBehavior = 'auto'")
    height = page.evaluate("document.documentElement.scrollHeight")
    viewport = page.evaluate("window.innerHeight")
    for position in range(0, height, max(1, viewport // 2)):
        page.evaluate("(y) => window.scrollTo(0, y)", position)
        page.wait_for_timeout(120)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(300)


def screenshot_set(browser, url: str, out: Path, version: str, view: str,
                   viewport: dict[str, int], mobile: bool) -> list[str]:
    context = browser.new_context(
        viewport=viewport,
        is_mobile=mobile,
        has_touch=mobile,
        device_scale_factor=2 if mobile else 1,
    )
    page = context.new_page()
    page.goto(f"{url.rstrip('/')}/products/", wait_until="networkidle")
    reveal_page(page)

    paths = [
        f"{version}-{view}-first-screen.png",
        f"{version}-{view}-full-page.png",
        f"{version}-{view}-profile-area.png",
        f"{version}-{view}-design-area.png",
        f"{version}-{view}-performance-area.png",
        f"{version}-{view}-footer-area.png",
    ]
    page.screenshot(path=str(out / paths[0]))
    page.screenshot(path=str(out / paths[1]), full_page=True)
    page.locator("#product-technology").screenshot(path=str(out / paths[2]))
    page.locator(".design-scene").screenshot(path=str(out / paths[3]))
    page.locator(".performance-scene").screenshot(path=str(out / paths[4]))
    page.locator(".site-footer").screenshot(path=str(out / paths[5]))
    context.close()
    return paths


def scroll_recording(browser, url: str, out: Path, version: str, view: str,
                     viewport: dict[str, int], mobile: bool) -> str:
    video_dir = out / f"video-{version}-{view}"
    video_dir.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(
        viewport=viewport,
        is_mobile=mobile,
        has_touch=mobile,
        device_scale_factor=2 if mobile else 1,
        record_video_dir=str(video_dir),
        record_video_size=viewport,
    )
    page = context.new_page()
    page.goto(f"{url.rstrip('/')}/products/", wait_until="networkidle")
    page.wait_for_timeout(500)

    if mobile:
        session = context.new_cdp_session(page)
        x = viewport["width"] / 2
        height = viewport["height"]

        def touch_scroll(direction: int) -> None:
            start_y = height * (0.72 if direction < 0 else 0.24)
            y_delta = direction * height * 0.48
            session.send("Input.dispatchTouchEvent", {
                "type": "touchStart",
                "touchPoints": [{"x": x, "y": start_y}],
            })
            for step in range(1, 9):
                session.send("Input.dispatchTouchEvent", {
                    "type": "touchMove",
                    "touchPoints": [{"x": x, "y": start_y + y_delta * step / 8}],
                })
                page.wait_for_timeout(16)
            session.send("Input.dispatchTouchEvent", {
                "type": "touchEnd",
                "touchPoints": [],
            })
            page.wait_for_timeout(180)

        max_scroll = page.evaluate(
            "document.documentElement.scrollHeight - window.innerHeight")
        for direction, done in ((-1, lambda y: y >= max_scroll - 2),
                                (1, lambda y: y <= 0)):
            last_y = page.evaluate("window.scrollY")
            stalled = 0
            while not done(last_y) and stalled < 3:
                before = last_y
                touch_scroll(direction)
                last_y = page.evaluate("window.scrollY")
                stalled = stalled + 1 if last_y == before else 0
            if not done(last_y):
                raise RuntimeError(
                    f"mobile touch scroll did not reach {'bottom' if direction < 0 else 'top'}; "
                    f"scrollY={last_y}, max={max_scroll}")
        session.detach()
    else:
        for delta in (650, 650, 650, 650, 650, 650, -650, -650, -650, -650, -650, -650):
            page.mouse.wheel(0, delta)
            page.wait_for_timeout(220)

    video = page.video.path()
    context.close()
    target = out / f"{version}-{view}-scroll.webm"
    Path(video).replace(target)
    video_dir.rmdir()
    return target.name


def capture_version(browser, url: str, out: Path, version: str) -> dict:
    result = {"url": url, "screenshots": {}, "recordings": {}}
    for view, viewport, mobile in (
        ("desktop-1440x900", {"width": 1440, "height": 900}, False),
        ("mobile-390x844", {"width": 390, "height": 844}, True),
    ):
        result["screenshots"][view] = screenshot_set(
            browser, url, out, version, view, viewport, mobile)
        result["recordings"][view] = scroll_recording(
            browser, url, out, version, view, viewport, mobile)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-url", default="http://127.0.0.1:4174")
    parser.add_argument("--after-url", default="http://127.0.0.1:4173")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        evidence = {
            "comparison": {
                "A": "c69080fd84dc4c7f629f1247644841bbbf80ca7f",
                "B": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], text=True).strip(),
            },
            "viewports": {
                "desktop": "1440x900",
                "mobile": "390x844 (emulated; not a physical phone)",
            },
            "browser": "Playwright Chromium",
            "A": capture_version(browser, args.before_url, args.out, "A-before"),
            "B": capture_version(browser, args.after_url, args.out, "B-after"),
            "limitations": ["Mobile uses browser emulation, not physical-device testing."],
        }
        browser.close()

    manifest = args.out / "products-ab-evidence.json"
    manifest.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    print(f"Evidence manifest: {manifest}")


if __name__ == "__main__":
    main()
