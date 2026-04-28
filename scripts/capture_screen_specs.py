#!/usr/bin/env python3
"""capture_screen_specs.py — Reproducible screenshot capture for screen specs.

Usage:
    python scripts/capture_screen_specs.py [home]

Captures all screenshots referenced by docs/internal/front/screens/docs-screen-*.html
into docs/internal/front/screens/assets/. Designed to be re-run on every change to a
screen so the gallery stays current.

Requirements:
    pip install playwright
    playwright install webkit

Why WebKit and not Chromium:
    WebKit is bundled with Playwright for macOS at half the download size and runs
    headless without requiring Xcode. Cross-engine pixel parity is unnecessary for
    documentation evidence — all that matters is a reproducible recent capture.

Conventions:
    - Output files: <screen-id>-<variant>.png, kebab-case.
    - Variants: desktop-light, desktop-dark, tablet, mobile, intro-phase-N, full.
    - Always 2x device pixel ratio (mobile uses 3x to match common phone DPRs).
    - The local docs/ folder is served via http.server on a random localhost port
      so file:// quirks (relative imports, theme storage) don't apply.
"""

from __future__ import annotations

import http.server
import os
import socket
import socketserver
import sys
import threading
import time
from pathlib import Path

DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"
ASSETS_DIR = DOCS_ROOT / "internal/front/screens/assets"
ASSETS_DIR.mkdir(parents=True, exist_ok=True)

# Init script injected into every page context. Sets the theme preference and
# overrides matchMedia so prefers-reduced-motion: reduce never matches —
# essential for capturing motion-driven UI (intro overlay, decrypt, etc.) in
# headless WebKit, which otherwise reports reduced-motion by default.
MOTION_OK_INIT = (
    "try{{localStorage.setItem('docs-theme-preference','{theme}')}}catch(e){{}}"
    "Object.defineProperty(window,'matchMedia',{{value:function(q){{"
    "return {{matches:false,media:q,"
    "addListener:function(){{}},removeListener:function(){{}},"
    "addEventListener:function(){{}},removeEventListener:function(){{}},"
    "dispatchEvent:function(){{return false}},onchange:null}}}},"
    "configurable:true}});"
)


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def serve_docs(port: int):
    os.chdir(DOCS_ROOT)
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def capture_home(base_url: str):
    """Capture all home-page variants required by the home-landing screen spec."""
    from playwright.sync_api import sync_playwright

    url = f"{base_url}/index.html"
    print(f"Capturing home page from {url}")

    def shoot(page, fname, full_page=False, clip=None):
        kwargs = {"path": str(ASSETS_DIR / fname), "type": "png"}
        if clip:
            kwargs["clip"] = clip
        if full_page:
            kwargs["full_page"] = True
        page.screenshot(**kwargs)
        print(f"  → {fname}")

    with sync_playwright() as p:
        browser = p.webkit.launch()

        # ── Desktop · light ─────────────────────────────────────────
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            color_scheme="light",
            reduced_motion="no-preference",
        )
        page = ctx.new_page()
        page.add_init_script(MOTION_OK_INIT.format(theme="light"))
        page.goto(url)
        page.wait_for_timeout(700)  # mid-scramble (headless WebKit runs animations fast)
        shoot(
            page,
            "home-desktop-light-intro.png",
            clip={"x": 0, "y": 0, "width": 1440, "height": 900},
        )
        page.evaluate("document.querySelector('[data-home-intro-skip]')?.click()")
        page.wait_for_timeout(900)
        shoot(
            page, "home-desktop-light-hero.png", clip={"x": 0, "y": 0, "width": 1440, "height": 900}
        )
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        shoot(page, "home-desktop-light-full.png", full_page=True)
        ctx.close()

        # ── Desktop · dark ──────────────────────────────────────────
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            color_scheme="dark",
            reduced_motion="no-preference",
        )
        page = ctx.new_page()
        page.add_init_script(MOTION_OK_INIT.format(theme="dark"))
        page.goto(url)
        page.wait_for_timeout(1300)
        shoot(
            page, "home-desktop-dark-intro.png", clip={"x": 0, "y": 0, "width": 1440, "height": 900}
        )
        page.evaluate("document.querySelector('[data-home-intro-skip]')?.click()")
        page.wait_for_timeout(900)
        shoot(
            page, "home-desktop-dark-hero.png", clip={"x": 0, "y": 0, "width": 1440, "height": 900}
        )
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(300)
        shoot(page, "home-desktop-dark-full.png", full_page=True)
        ctx.close()

        # ── Intro phases (desktop · dark) ───────────────────────────
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            device_scale_factor=2,
            color_scheme="dark",
            reduced_motion="no-preference",
        )
        page = ctx.new_page()
        page.add_init_script(MOTION_OK_INIT.format(theme="dark"))
        page.goto(url)
        page.wait_for_timeout(450)
        shoot(
            page,
            "home-intro-phase-1-early.png",
            clip={"x": 0, "y": 0, "width": 1440, "height": 900},
        )
        page.wait_for_timeout(900)
        shoot(
            page, "home-intro-phase-2-mid.png", clip={"x": 0, "y": 0, "width": 1440, "height": 900}
        )
        page.wait_for_timeout(800)
        shoot(
            page,
            "home-intro-phase-3-locked.png",
            clip={"x": 0, "y": 0, "width": 1440, "height": 900},
        )
        ctx.close()

        # ── Tablet ──────────────────────────────────────────────────
        ctx = browser.new_context(
            viewport={"width": 1024, "height": 900},
            device_scale_factor=2,
            color_scheme="dark",
            reduced_motion="no-preference",
        )
        page = ctx.new_page()
        page.add_init_script(MOTION_OK_INIT.format(theme="dark"))
        page.goto(url)
        page.wait_for_timeout(1300)
        shoot(page, "home-tablet-intro.png", clip={"x": 0, "y": 0, "width": 1024, "height": 900})
        page.evaluate("document.querySelector('[data-home-intro-skip]')?.click()")
        page.wait_for_timeout(900)
        shoot(page, "home-tablet-hero.png", clip={"x": 0, "y": 0, "width": 1024, "height": 900})
        ctx.close()

        # ── Mobile ──────────────────────────────────────────────────
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=3,
            color_scheme="dark",
            reduced_motion="no-preference",
        )
        page = ctx.new_page()
        page.add_init_script(MOTION_OK_INIT.format(theme="dark"))
        page.goto(url)
        page.wait_for_timeout(1300)
        shoot(page, "home-mobile-intro.png", clip={"x": 0, "y": 0, "width": 390, "height": 844})
        page.evaluate("document.querySelector('[data-home-intro-skip]')?.click()")
        page.wait_for_timeout(900)
        shoot(page, "home-mobile-hero.png", clip={"x": 0, "y": 0, "width": 390, "height": 844})
        ctx.close()

        browser.close()


def main():
    targets = sys.argv[1:] or ["home"]
    port = find_free_port()
    httpd = serve_docs(port)
    base_url = f"http://127.0.0.1:{port}"
    time.sleep(0.5)
    try:
        for target in targets:
            if target == "home":
                capture_home(base_url)
            else:
                print(f"  skipping unknown target: {target}", file=sys.stderr)
    finally:
        httpd.shutdown()
    print(f"\nDone. Output: {ASSETS_DIR}")


if __name__ == "__main__":
    main()
