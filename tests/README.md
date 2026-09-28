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

# homepage screenshots, scroll recordings and load comparison
.venv\Scripts\python tools\capture_evidence.py --out evidence --baseline-root <baseline docs folder>

# isolated A/B Products previews (A is the pre-redesign c69080f version)
git worktree add ..\products-before c69080fd84dc4c7f629f1247644841bbbf80ca7f
# In a second terminal, from ..\products-before:
python tools\serve.py --port 4174
# From this feature worktree in another terminal:
python tools\serve.py --port 4173
# Open A at http://127.0.0.1:4174/products/ and B at http://127.0.0.1:4173/products/

# matched Products A/B screenshots (first screen, profile area, full page) and real-scroll recordings
python tools\capture_products_evidence.py --before-url http://127.0.0.1:4174 --after-url http://127.0.0.1:4173 --out evidence\products-ab
```

Browser emulation (viewports, touch, reduced motion, throttling) is not a substitute for testing on real phones.
