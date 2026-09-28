# Site tests and local preview

The published site is the static `docs/` folder (GitHub Pages, `main` branch `/docs`).
Nothing in `tests/`, `tools/` or `.github/workflows/preview-tests.yml` is published or deploys anything.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-dev.txt
.venv\Scripts\python -m playwright install chromium firefox webkit

# isolated local preview (binds to 127.0.0.1 only)
.venv\Scripts\python tools\serve.py --port 4173   # http://127.0.0.1:4173/

# end-to-end tests (starts the preview server automatically if the port is free)
.venv\Scripts\python -m pytest tests --browser chromium --browser firefox --browser webkit -q

# regenerate responsive images from the untouched originals in docs/assets/
.venv\Scripts\python tools\optimize_images.py

# screenshots, scroll recordings and before/after load comparison
.venv\Scripts\python tools\capture_evidence.py --out evidence --baseline-root <baseline docs folder>

# Products page screenshots and sample/lightbox interaction recordings
.venv\Scripts\python tools\capture_products_evidence.py --out evidence\products
```

Browser emulation (viewports, touch, reduced motion, throttling) is not a substitute for testing on real phones.
