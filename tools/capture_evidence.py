"""Capture review evidence: key-position screenshots, a continuous-scroll recording and a
before/after load comparison (baseline docs vs this branch) under identical emulated conditions.

Usage:
  python tools/capture_evidence.py --out <dir> [--baseline-root <path to baseline docs>]

The baseline docs can be produced with:
  git archive -o base.tar <BASE_SHA> docs && tar -xf base.tar -C <dir>
Outputs are written outside the published docs/ folder. Emulation is not a real device.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

PERF_OBSERVER = """
window.__perf = { lcp: 0, lcpUrl: '', cls: 0 };
new PerformanceObserver((list) => {
  for (const e of list.getEntries()) { window.__perf.lcp = e.startTime; window.__perf.lcpUrl = e.url || (e.element && e.element.tagName) || ''; }
}).observe({ type: 'largest-contentful-paint', buffered: true });
new PerformanceObserver((list) => {
  for (const e of list.getEntries()) { if (!e.hadRecentInput) window.__perf.cls += e.value; }
}).observe({ type: 'layout-shift', buffered: true });
"""


def start_server(root: Path, port: int):
    proc = subprocess.Popen([sys.executable, str(ROOT / "tools" / "serve.py"), "--root", str(root), "--port", str(port)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    return proc


def settle(page):
    page.evaluate("""() => new Promise((r) => { let l = -1, s = 0; const t = () => { const y = scrollY;
        s = y === l ? s + 1 : 0; l = y; s >= 4 ? r() : requestAnimationFrame(t); }; t(); })""")


def screenshots(browser, base: str, out: Path, label: str):
    out.mkdir(parents=True, exist_ok=True)
    shots = []
    configs = {
        "desktop-1440": dict(viewport={"width": 1440, "height": 900}),
        "mobile-390": dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2),
    }
    for name, opts in configs.items():
        ctx = browser.new_context(**opts)
        page = ctx.new_page()
        for page_key, path in (("home", "/"), ("products", "/products/"), ("contact", "/contact/")):
            page.goto(base + path, wait_until="networkidle")
            page.wait_for_timeout(900)
            file = out / f"{label}-{name}-{page_key}-top.png"
            page.screenshot(path=str(file))
            shots.append(file.name)
        page.goto(base + "/", wait_until="networkidle")
        anchors = {"gallery": "#explore-products", "process": "#technology", "design": "#design-customization",
                   "performance": "#performance"}
        for key, selector in anchors.items():
            if not page.locator(selector).count():
                continue
            page.evaluate("(s) => window.scrollTo({top: document.querySelector(s).getBoundingClientRect().top + scrollY, behavior: 'instant'})", selector)
            settle(page)
            page.wait_for_timeout(900)
            file = out / f"{label}-{name}-home-{key}.png"
            page.screenshot(path=str(file))
            shots.append(file.name)
            if key == "process" and name.startswith("desktop"):
                vh = page.viewport_size["height"]
                for i in (1, 2, 3):
                    page.mouse.wheel(0, vh * 0.55)
                    settle(page)
                    page.wait_for_timeout(800)
                    file = out / f"{label}-{name}-home-process-step{i + 1}.png"
                    page.screenshot(path=str(file))
                    shots.append(file.name)
        page.evaluate("window.scrollTo({top: document.documentElement.scrollHeight, behavior: 'instant'})")
        settle(page)
        page.wait_for_timeout(900)
        file = out / f"{label}-{name}-home-end.png"
        page.screenshot(path=str(file))
        shots.append(file.name)
        ctx.close()
    return shots


def record_scroll(browser, base: str, out: Path, label: str, viewport, mobile=False):
    video_dir = out / f"video-{label}"
    opts = dict(viewport=viewport, record_video_dir=str(video_dir), record_video_size=viewport)
    if mobile:
        opts.update(is_mobile=True, has_touch=True, device_scale_factor=2)
    ctx = browser.new_context(**opts)
    page = ctx.new_page()
    page.goto(base + "/", wait_until="networkidle")
    page.wait_for_timeout(600)
    page.mouse.move(viewport["width"] / 2, viewport["height"] / 2)
    total = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    y = 0
    while y < total:
        if mobile:
            page.evaluate("window.scrollBy(0, 60)")
        else:
            page.mouse.wheel(0, 90)
        page.wait_for_timeout(35)
        y = page.evaluate("scrollY")
        total = page.evaluate("document.documentElement.scrollHeight - innerHeight")
    page.wait_for_timeout(600)
    video = page.video.path()
    ctx.close()
    target = out / f"{label}-scroll.webm"
    Path(video).replace(target)
    video_dir.rmdir()
    return target.name


def measure_load(p, base: str, runs: int, mobile: bool):
    """Cold load in Chromium with CDP network + CPU throttling. Returns median metrics."""
    browser = p.chromium.launch()
    results = []
    for _ in range(runs):
        opts = dict(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=3) if mobile \
            else dict(viewport={"width": 1440, "height": 900})
        ctx = browser.new_context(**opts)
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        # ~"Fast 4G"-like profile: 40 ms RTT, 9 Mbit/s down, 1.5 Mbit/s up
        cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 40,
                                                        "downloadThroughput": 9_000_000 / 8,
                                                        "uploadThroughput": 1_500_000 / 8})
        cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4 if mobile else 1})
        encoded = {"bytes": 0, "requests": 0}

        def on_loading_finished(params):
            encoded["bytes"] += params.get("encodedDataLength", 0)
            encoded["requests"] += 1

        cdp.on("Network.loadingFinished", on_loading_finished)
        page.add_init_script(PERF_OBSERVER)
        start = time.time()
        page.goto(base + "/", wait_until="load", timeout=600_000)
        load_s = time.time() - start
        page.wait_for_timeout(2500)
        initial = dict(encoded)
        perf = page.evaluate("window.__perf")
        fcp = page.evaluate("(performance.getEntriesByName('first-contentful-paint')[0] || {startTime: 0}).startTime")
        hero = page.evaluate("""() => { const r = performance.getEntriesByType('resource')
            .filter((e) => e.name.includes('20260318184938_644_41')); return r.length ? Math.max(...r.map((e) => e.responseEnd)) : null; }""")
        nav = page.evaluate("JSON.parse(JSON.stringify(performance.getEntriesByType('navigation')[0]))")
        # full native scroll to the page end so lazy resources load, then count total bytes
        total = page.evaluate("document.documentElement.scrollHeight - innerHeight")
        y = 0
        while y < total:
            page.evaluate("window.scrollBy(0, innerHeight * 0.6)")
            page.wait_for_timeout(120)
            y = page.evaluate("scrollY")
            total = page.evaluate("document.documentElement.scrollHeight - innerHeight")
        try:
            page.wait_for_load_state("networkidle", timeout=600_000)
        except Exception:
            pass
        page.wait_for_timeout(1000)
        results.append({
            "fcp_ms": round(fcp), "hero_image_ms": round(hero) if hero else None, "lcp_ms": round(perf["lcp"]), "lcp_element": perf["lcpUrl"][-60:], "cls": round(perf["cls"], 4),
            "load_event_ms": round(nav["loadEventEnd"]), "load_wall_s": round(load_s, 2),
            "initial_bytes": initial["bytes"], "initial_requests": initial["requests"],
            "full_scroll_bytes": encoded["bytes"], "full_scroll_requests": encoded["requests"],
        })
        ctx.close()
    browser.close()
    results.sort(key=lambda r: r["lcp_ms"])
    return {"median": results[len(results) // 2], "runs": results}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--baseline-root")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--skip-perf", action="store_true")
    parser.add_argument("--perf-only", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    servers = {"after": (ROOT / "docs", 4191)}
    if args.baseline_root:
        servers["before"] = (Path(args.baseline_root), 4192)
    procs = [start_server(root, port) for root, port in servers.values()]
    report = {}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for label, (_, port) in ([] if args.perf_only else servers.items()):
                base = f"http://127.0.0.1:{port}"
                report.setdefault(label, {})["screenshots"] = screenshots(browser, base, out / "screenshots", label)
                if label == "after":
                    report[label]["video_desktop"] = record_scroll(browser, base, out, "after-desktop-1440",
                                                                   {"width": 1440, "height": 900})
                    report[label]["video_mobile"] = record_scroll(browser, base, out, "after-mobile-390",
                                                                  {"width": 390, "height": 844}, mobile=True)
            browser.close()
            if not args.skip_perf:
                for label, (_, port) in servers.items():
                    base = f"http://127.0.0.1:{port}"
                    report.setdefault(label, {})["perf_desktop"] = measure_load(p, base, args.runs, mobile=False)
                    report[label]["perf_mobile"] = measure_load(p, base, args.runs, mobile=True)
    finally:
        for proc in procs:
            proc.terminate()
    name = "perf.json" if args.perf_only else "evidence.json"
    (out / name).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: {m: v[m]["median"] for m in v if m.startswith("perf")} for k, v in report.items()}, indent=2))


if __name__ == "__main__":
    main()
