"""End-to-end checks for the isolated homepage preview (docs/ served locally).

Run: python -m pytest tests --browser chromium --browser firefox --browser webkit
Emulated viewports/touch are NOT a substitute for real devices.
"""
import re

import pytest

from conftest import PageProbe, VIEWPORTS

PAGES = {"home": "/", "products": "/products/", "contact": "/contact/"}


def settle(page, timeout_ms=1500):
    """Wait until window.scrollY stops changing (native smooth scrolling may animate)."""
    return page.evaluate(
        """(timeout) => new Promise((resolve) => {
            let last = -1, stable = 0; const start = performance.now();
            const tick = () => {
              const y = window.scrollY;
              stable = (y === last) ? stable + 1 : 0; last = y;
              if (stable >= 4 || performance.now() - start > timeout) resolve(y);
              else requestAnimationFrame(tick);
            };
            tick();
        })""",
        timeout_ms,
    )


def max_scroll(page):
    return page.evaluate("document.documentElement.scrollHeight - window.innerHeight")


def scroll_to(page, y):
    page.evaluate("(y) => window.scrollTo({top: y, behavior: 'instant'})", y)
    return settle(page)


def load_all_images(page):
    """Scroll the entire page natively so lazy images load, then verify every <img> decoded."""
    total = max_scroll(page)
    step = max(200, page.viewport_size["height"] // 2)
    y = 0
    while y < total:
        y = min(total, y + step)
        scroll_to(page, y)
        page.wait_for_timeout(60)
        total = max_scroll(page)
    page.wait_for_load_state("networkidle")
    broken = page.evaluate(
        """async () => {
            const imgs = Array.from(document.images);
            await Promise.all(imgs.map((img) => img.complete ? null : new Promise((r) => { img.onload = img.onerror = r; })));
            return imgs.filter((img) => !(img.complete && img.naturalWidth > 0)).map((img) => img.currentSrc || img.src);
        }"""
    )
    assert not broken, f"images failed to load: {broken}"


def no_horizontal_overflow(page):
    return page.evaluate(
        "Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) <= window.innerWidth + 1"
    )


@pytest.mark.parametrize("page_key", list(PAGES))
def test_direct_visit_clean(ctx_factory, base_url, viewport_name, page_key):
    page = ctx_factory(viewport_name).new_page()
    probe = PageProbe(page)
    page.goto(base_url + PAGES[page_key], wait_until="load")
    assert page.locator("h1").count() == 1
    assert page.locator("h1").is_visible()
    # every image must carry an alt attribute (decorative backgrounds use alt="")
    assert page.evaluate("Array.from(document.images).every((i) => i.hasAttribute('alt'))")
    # heading levels never skip (h1 -> h2 ...)
    levels = page.evaluate("Array.from(document.querySelectorAll('h1,h2,h3,h4')).map((h) => +h.tagName[1])")
    assert levels[0] == 1 and all(b - a <= 1 for a, b in zip(levels, levels[1:])), levels
    assert no_horizontal_overflow(page), "horizontal overflow at top"
    load_all_images(page)
    assert no_horizontal_overflow(page), "horizontal overflow after scrolling"
    # the page end (footer or last scene) is reachable
    assert settle(page) >= max_scroll(page) - 2
    # nothing covers the primary heading
    scroll_to(page, 0)
    page.wait_for_timeout(900)
    covered = page.evaluate(
        """() => { const h = document.querySelector('h1'); const r = h.getBoundingClientRect();
                  if (r.width < 2) return false;  // visually-hidden heading
                  const el = document.elementFromPoint(r.left + Math.min(40, r.width / 2), r.top + r.height / 2);
                  return !(el && (h === el || h.contains(el))); }"""
    )
    assert not covered, "h1 is covered by another element"
    probe.assert_clean()


def test_navigation_and_legacy_redirects(ctx_factory, base_url, viewport_name):
    page = ctx_factory(viewport_name).new_page()
    probe = PageProbe(page)
    page.goto(base_url + "/")
    nav = page.get_by_role("navigation", name="Primary")
    nav.get_by_role("link", name="Products").click()
    page.wait_for_url(re.compile(r"/products/$"))
    assert page.locator("a[aria-current='page']").inner_text().strip().lower() == "products"
    nav = page.get_by_role("navigation", name="Primary")
    nav.get_by_role("link", name="Contact").click()
    page.wait_for_url(re.compile(r"/contact/$"))
    nav = page.get_by_role("navigation", name="Primary")
    nav.get_by_role("link", name="Home").click()
    page.wait_for_url(re.compile(r"/$"))
    for legacy, target in (("/products.html", r"/products/$"), ("/contact.html", r"/contact/$")):
        page.goto(base_url + legacy)
        page.wait_for_url(re.compile(target))
    probe.assert_clean()


def test_wheel_scroll_passes_gallery_without_trap(ctx_factory, base_url, viewport_name):
    if viewport_name.startswith(("mobile", "tablet")):
        pytest.skip("wheel is a desktop input; touch covered separately")
    page = ctx_factory(viewport_name).new_page()
    probe = PageProbe(page)
    page.goto(base_url + "/")
    stage = page.locator("[data-gallery]")
    gallery_top = page.evaluate("document.querySelector('#explore-products').getBoundingClientRect().top + scrollY")
    scroll_to(page, gallery_top - 100)
    box = stage.bounding_box()
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    start_index = stage.get_attribute("data-index")
    last = settle(page)
    for _ in range(8):
        page.mouse.wheel(0, 240)
        y = settle(page)
        assert y > last, "wheel over gallery did not scroll the page (scroll trap)"
        last = y
    assert stage.get_attribute("data-index") == start_index, "vertical wheel changed the gallery slide"
    # keep wheeling to the very end of the page, then back up
    for _ in range(200):
        if last >= max_scroll(page) - 2:
            break
        page.mouse.wheel(0, 400)
        last = settle(page)
    assert last >= max_scroll(page) - 2, "could not reach page end with wheel"
    assert page.locator(".site-footer").is_visible()
    for _ in range(200):
        if last <= 0:
            break
        page.mouse.wheel(0, -600)
        last = settle(page)
    assert last == 0
    probe.assert_clean()


def test_keyboard_scroll_and_gallery_focus(ctx_factory, base_url, viewport_name):
    page = ctx_factory(viewport_name).new_page()
    probe = PageProbe(page)
    page.goto(base_url + "/")
    box = page.locator("h1").bounding_box()
    page.mouse.click(box["x"] + 4, box["y"] + box["height"] / 2)
    y0 = settle(page)
    page.keyboard.press("PageDown")
    page.wait_for_function("(y0) => window.scrollY > y0", arg=y0, timeout=3000)
    y1 = settle(page)
    assert y1 > y0
    page.keyboard.press("End")
    assert settle(page, 3000) >= max_scroll(page) - 2
    page.keyboard.press("Home")
    assert settle(page, 3000) == 0

    stage = page.locator("[data-gallery]")
    # arrow keys without gallery focus do nothing to the gallery
    page.keyboard.press("ArrowRight")
    assert stage.get_attribute("data-index") == "0"
    stage.focus()
    page.keyboard.press("ArrowRight")
    assert stage.get_attribute("data-index") == "1"
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("ArrowLeft")
    assert stage.get_attribute("data-index") == "4"
    # buttons still work and are reachable
    page.locator("[data-gallery-next]").click()
    assert stage.get_attribute("data-index") == "0"
    assert page.locator("[data-gallery-title]").inner_text() == "Black anodized frame details."
    # Tab order reaches the gallery controls and the stage
    focusables = page.evaluate(
        """() => Array.from(document.querySelectorAll('a[href], button, [tabindex="0"]'))
               .filter((el) => el.offsetParent !== null || getComputedStyle(el).position === 'fixed')
               .map((el) => el.textContent.trim() || el.getAttribute('aria-label'))"""
    )
    assert "Prev" in focusables and "Next" in focusables and "Product gallery" in focusables
    probe.assert_clean()


def test_touch_swipe_gallery_and_vertical_touch_scroll(ctx_factory, base_url, browser_name):
    page = ctx_factory("mobile-390").new_page()
    probe = PageProbe(page)
    page.goto(base_url + "/")
    stage = page.locator("[data-gallery]")
    stage.scroll_into_view_if_needed()
    settle(page)

    def swipe(dx, dy):
        page.evaluate(
            """([dx, dy]) => {
                const el = document.querySelector('[data-gallery]'); const r = el.getBoundingClientRect();
                const x = r.left + r.width / 2, y = r.top + r.height / 2;
                const mk = (cx, cy) => ({identifier: 1, target: el, clientX: cx, clientY: cy});
                const fire = (type, touch) => {
                  // WebKit on Windows has no Touch constructor; a plain Event with the same shape
                  // exercises the same listener code path.
                  const ev = new Event(type, {bubbles: true});
                  Object.defineProperty(ev, 'changedTouches', {value: [touch]});
                  el.dispatchEvent(ev);
                };
                fire('touchstart', mk(x, y));
                fire('touchend', mk(x + dx, y + dy));
            }""",
            [dx, dy],
        )

    swipe(-120, 6)
    assert stage.get_attribute("data-index") == "1", "horizontal swipe should advance"
    swipe(10, -160)
    assert stage.get_attribute("data-index") == "1", "vertical swipe must not change slide"
    assert page.evaluate("getComputedStyle(document.querySelector('[data-gallery]')).touchAction") == "pan-y"

    if browser_name == "chromium":
        # Browser-level touch drag starting on the gallery (Chromium CDP only; emulation, not a real phone).
        cdp = page.context.new_cdp_session(page)
        box = stage.bounding_box()
        x = box["x"] + box["width"] / 2
        y = min(box["y"] + box["height"] / 2, 700)
        before = settle(page)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
        for i in range(1, 21):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": x, "y": y - i * 20}]})
            page.wait_for_timeout(16)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        after = settle(page)
        assert after > before + 200, f"touch scroll over gallery blocked ({before} -> {after})"
        assert stage.get_attribute("data-index") == "1"
    probe.assert_clean()


@pytest.mark.parametrize("vp", ["desktop-1440", "desktop-1920"])
def test_sticky_process_enters_pins_and_exits(ctx_factory, base_url, vp):
    page = ctx_factory(vp).new_page()
    probe = PageProbe(page)
    page.goto(base_url + "/")
    section = page.locator("[data-process]")
    assert "is-enhanced" in section.get_attribute("class")
    top = page.evaluate("document.querySelector('[data-process]').getBoundingClientRect().top + scrollY")
    height = page.evaluate("document.querySelector('[data-process]').offsetHeight")
    vh = VIEWPORTS[vp]["height"]
    assert height < vh * 3.2, f"sticky section too long ({height}px)"

    def media_top():
        return page.evaluate(
            "document.querySelector('[data-process-media].is-active').getBoundingClientRect().top")

    seen_steps = []
    pinned_tops = []
    # natural (unpinned) position before the sticky phase starts
    scroll_to(page, top - vh * 0.5)
    unpinned_before = media_top()
    y = top + vh * 0.25
    while y < top + height - vh:
        scroll_to(page, y)
        page.wait_for_timeout(80)
        seen_steps.append(int(section.get_attribute("data-active-step")))
        pinned_tops.append(media_top())
        y += vh * 0.25
    assert seen_steps == sorted(seen_steps), f"steps not sequential: {seen_steps}"
    assert set(seen_steps) == {1, 2, 3, 4}, seen_steps
    assert max(pinned_tops) - min(pinned_tops) < 2, f"media not pinned: {pinned_tops}"
    assert unpinned_before > pinned_tops[0] + vh * 0.3, "media should enter with the page before pinning"
    # the active step text is fully visible
    page.wait_for_timeout(700)
    assert page.evaluate("getComputedStyle(document.querySelector('[data-process-step].is-active')).opacity") == "1"
    # after the section, media scrolls away with the page (no lock)
    scroll_to(page, top + height)
    assert media_top() < 0
    probe.assert_clean()


@pytest.mark.parametrize("vp", ["tablet-768", "mobile-390"])
def test_small_screens_use_static_layout(ctx_factory, base_url, vp):
    page = ctx_factory(vp).new_page()
    probe = PageProbe(page)
    page.goto(base_url + "/")
    section = page.locator("[data-process]")
    assert "is-enhanced" not in section.get_attribute("class")
    for figure in section.locator("[data-process-media]").all():
        figure.scroll_into_view_if_needed()
        assert figure.evaluate("(el) => getComputedStyle(el).opacity") == "1"
        assert figure.evaluate("(el) => getComputedStyle(el).position") != "sticky"
    if vp == "mobile-390":
        transforms = page.evaluate(
            "Array.from(document.querySelectorAll('.parallax-target')).map((el) => el.style.getPropertyValue('--parallax-y'))")
        assert all(t == "" for t in transforms), "parallax should be off on small screens"
    probe.assert_clean()


def _wait_enhanced(page, expected, timeout=3000):
    page.wait_for_function(
        "(exp) => document.querySelector('[data-process]').classList.contains('is-enhanced') === exp",
        arg=expected, timeout=timeout)


def test_resize_orientation_and_reduced_motion_switching(ctx_factory, base_url):
    ctx = ctx_factory("desktop-1440")
    page = ctx.new_page()
    probe = PageProbe(page)
    page.goto(base_url + "/")
    section = page.locator("[data-process]")
    scroll_to(page, 400)
    page.wait_for_timeout(100)
    assert page.evaluate("document.documentElement.classList.contains('parallax-on')")
    assert page.evaluate("document.querySelector('.hero-photo-fill').style.getPropertyValue('--parallax-y')") != ""

    page.set_viewport_size({"width": 390, "height": 844})
    _wait_enhanced(page, False)
    page.wait_for_function("() => document.querySelector('.hero-photo-fill').style.getPropertyValue('--parallax-y') === ''", timeout=3000)
    assert "is-enhanced" not in section.get_attribute("class")
    assert page.evaluate("document.querySelector('.hero-photo-fill').style.getPropertyValue('--parallax-y')") == ""
    assert no_horizontal_overflow(page)

    page.set_viewport_size({"width": 844, "height": 390})  # phone landscape
    page.wait_for_timeout(200)
    assert "is-enhanced" not in section.get_attribute("class")
    assert no_horizontal_overflow(page)

    page.set_viewport_size({"width": 1440, "height": 900})
    _wait_enhanced(page, True)
    assert "is-enhanced" in section.get_attribute("class")

    page.emulate_media(reduced_motion="reduce")
    _wait_enhanced(page, False)
    page.wait_for_function("() => !document.documentElement.classList.contains('parallax-on')", timeout=3000)
    assert "is-enhanced" not in section.get_attribute("class")
    assert not page.evaluate("document.documentElement.classList.contains('parallax-on')")
    assert page.evaluate("getComputedStyle(document.querySelector('.hero-photo-fill')).transform") in ("none", "matrix(1, 0, 0, 1, 0, 0)")
    assert page.evaluate("Array.from(document.querySelectorAll('.reveal')).every((el) => getComputedStyle(el).opacity === '1')")

    page.emulate_media(reduced_motion="no-preference")
    _wait_enhanced(page, True)
    assert "is-enhanced" in section.get_attribute("class")
    probe.assert_clean()


def _all_content_visible(page):
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('.reveal, [data-process-step], [data-process-media], h1, h2'))
                .every((el) => { const s = getComputedStyle(el); return s.opacity === '1' && s.visibility !== 'hidden'; })"""
    )


@pytest.mark.parametrize("page_key", list(PAGES))
def test_content_visible_without_javascript(ctx_factory, base_url, page_key):
    page = ctx_factory("desktop-1440", java_script_enabled=False).new_page()
    page.goto(base_url + PAGES[page_key])
    page.wait_for_timeout(300)
    assert _all_content_visible(page)
    assert no_horizontal_overflow(page)


@pytest.mark.parametrize("failure", ["abort", "http500", "throws"])
def test_content_visible_when_main_script_fails(ctx_factory, base_url, failure):
    page = ctx_factory("desktop-1440").new_page()

    def handler(route):
        if failure == "abort":
            route.abort()
        elif failure == "http500":
            route.fulfill(status=500, body="error")
        else:
            route.fulfill(status=200, content_type="text/javascript",
                          body="throw new Error('simulated init failure');")

    page.route(re.compile(r"/script\.js"), handler)
    page.goto(base_url + "/")
    # abort usually fires onerror; some engines execute a 500 body as script, so visibility then
    # comes from the load-event fallback or, at worst, the CSS failsafe (3.5s).
    waited = 0
    while not _all_content_visible(page) and waited < 5000:
        page.wait_for_timeout(250)
        waited += 250
    assert _all_content_visible(page), f"content hidden {waited}ms after load ({failure})"
