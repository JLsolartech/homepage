import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PORT = int(os.environ.get("PREVIEW_PORT", "4173"))
BASE_URL = f"http://127.0.0.1:{PORT}"

VIEWPORTS = {
    "desktop-1440": {"width": 1440, "height": 900},
    "desktop-1920": {"width": 1920, "height": 1080},
    "tablet-768": {"width": 768, "height": 1024},
    "mobile-390": {"width": 390, "height": 844},
}


def _port_open(port: int) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) == 0


@pytest.fixture(scope="session")
def base_url():
    proc = None
    if not _port_open(PORT):
        proc = subprocess.Popen([sys.executable, str(ROOT / "tools" / "serve.py"), "--port", str(PORT)],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(100):
            if _port_open(PORT):
                break
            time.sleep(0.1)
        else:
            proc.kill()
            raise RuntimeError("preview server did not start")
    yield BASE_URL
    if proc:
        proc.terminate()


class PageProbe:
    """Collects console errors, page errors and failed/4xx requests for a page."""

    def __init__(self, page):
        self.page = page
        self.errors = []
        self.bad_responses = []
        self.failed_requests = []
        page.on("console", lambda msg: msg.type == "error" and self.errors.append(msg.text))
        page.on("pageerror", lambda err: self.errors.append(str(err)))
        page.on("response", lambda res: res.status >= 400 and self.bad_responses.append(f"{res.status} {res.url}"))
        page.on("requestfailed", lambda req: self.failed_requests.append(f"{req.failure} {req.url}"))

    def assert_clean(self):
        assert not self.errors, f"console/page errors: {self.errors}"
        assert not self.bad_responses, f"HTTP errors: {self.bad_responses}"
        assert not self.failed_requests, f"failed requests: {self.failed_requests}"


@pytest.fixture(params=list(VIEWPORTS), ids=list(VIEWPORTS))
def viewport_name(request):
    return request.param


def make_context(browser, viewport_name, **kwargs):
    vp = VIEWPORTS[viewport_name]
    mobile = viewport_name.startswith("mobile") or viewport_name.startswith("tablet")
    opts = {"viewport": vp}
    if mobile:
        opts["has_touch"] = True
        if browser.browser_type.name != "firefox":
            opts["is_mobile"] = True
            opts["device_scale_factor"] = 3 if viewport_name.startswith("mobile") else 2
    opts.update(kwargs)
    return browser.new_context(**opts)


@pytest.fixture
def ctx_factory(browser):
    contexts = []

    def factory(viewport_name, **kwargs):
        ctx = make_context(browser, viewport_name, **kwargs)
        contexts.append(ctx)
        return ctx

    yield factory
    for ctx in contexts:
        ctx.close()
