"""Render og/<item>.png: one 1200x630 link-preview card per policy and landmark,
og/line/<item>.png: the card's 3D snapshot alone, for the LINE Flex card's hero,
hero.jpg: a still panorama the page shows while the 3D scene loads, and og.png:
the site cover shown when the home page is shared.

The cards include a 3D snapshot, so the app draws them itself (index.html?og=policy-12)
and this script screenshots each one in headless Chromium. In ?og mode the app seeds its
random numbers and freezes the scenery, so the same code renders the same pixels.

GitHub Actions runs this on every push (.github/workflows/build.yml). To run it locally:

    pip install playwright pillow && playwright install chromium
    python3 tools/build_og_images.py && python3 tools/build_static.py
"""
import functools
import http.server
import re
import threading
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PORT = 8742

source = (ROOT / "index.html").read_text(encoding="utf-8")
n_policies = len(re.findall(r"short: '[^']+', title: '", source))
n_spots = len(re.findall(r"name: '[^']+', map: '", source))
items = [f"policy-{n:02d}" for n in range(1, n_policies + 1)] + [f"spot-{n:02d}" for n in range(1, n_spots + 1)]
# "cover" is the site cover; it is saved as og.png at the root instead of og/cover.png
items.append("cover")

# The snapshot sits at (56, 56), 518 px square, in makeOgCanvas; keep its middle 3:2 band.
# Flex shows the title and points as text, so the hero carries only the picture.
CROP_W, CROP_H, CROP_X, CROP_Y = 518, 345, 56, 56 + (518 - 345) // 2

handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
handler.log_message = lambda *a, **k: None
server = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

out = ROOT / "og"
line_out = out / "line"
line_out.mkdir(parents=True, exist_ok=True)
SEEN = "localStorage.setItem('islandHintSeen', '1'); localStorage.setItem('releaseSeen', '9999-12-31')"

try:
    with sync_playwright() as pw:
        # SwiftShader gives WebGL on machines without a GPU, such as CI runners
        browser = pw.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        page = browser.new_page(viewport={"width": 1200, "height": 630})
        page.add_init_script(SEEN)
        for key in items:
            page.goto(f"http://127.0.0.1:{PORT}/?og={key}")
            page.wait_for_function("window.ogReady === true", timeout=60_000)
            if key == "cover":
                page.screenshot(path=str(ROOT / "og.png"))
                print("rendered og.png")
                continue
            card = out / f"{key}.png"
            page.screenshot(path=str(card))
            with Image.open(card) as im:
                im.crop((CROP_X, CROP_Y, CROP_X + CROP_W, CROP_Y + CROP_H)).save(line_out / f"{key}.png", optimize=True)
            print("rendered", key)

        # Still panorama without any UI, shown by index.html while the 3D scene loads
        page.set_viewport_size({"width": 1600, "height": 1000})
        page.goto(f"http://127.0.0.1:{PORT}/?og=hero")
        page.wait_for_function("document.getElementById('loading').classList.contains('done')", timeout=60_000)
        page.wait_for_timeout(1000)
        page.evaluate("['header', 'footer', '#labels', '.scrim', '#toast', '#loading', '#rail', '#onboard'].forEach((q) => { const el = document.querySelector(q); if (el) el.style.display = 'none'; })")
        page.screenshot(path=str(out / "hero.png"))
        with Image.open(out / "hero.png") as im:
            im.convert("RGB").save(ROOT / "hero.jpg", quality=72, optimize=True)
        (out / "hero.png").unlink()
        print("rendered hero.jpg")
        browser.close()
finally:
    server.shutdown()
print(f"wrote {len(items)} images to {out}")
