#!/usr/bin/env python3
"""
AOG mockup screenshot script.
Renders all 5 HTML pages at desktop / tablet / mobile widths,
and captures ChatWidget open/closed states.

Usage:
  python3 screenshot.py            # full run, output to delivery/screenshots/T0.2/
  python3 screenshot.py --only home  # only specific scenes (home / city / experiences / experience / chat / 404)
"""
import os
import sys
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

# ---------- Config ----------
ROOT = Path(__file__).resolve().parent
MOCKUP = ROOT  # mockup dir contains index.html, city.html, etc.
OUT = Path("/Users/njx/Project/AOG知识库/project/AOG知识库网站/delivery/screenshots/T0.2")
OUT.mkdir(parents=True, exist_ok=True)

VIEWPORTS = {
    "desktop": (1280, 800),
    "tablet":  (768, 1024),
    "mobile":  (360, 640),
}

# Map filename -> html file
HTML_FILES = {
    "home":        "index.html",
    "city":        "city.html",
    "experiences": "experiences.html",
    "experience":  "experience.html",
    "404":         "404.html",
}

# Scene definitions: (label, page, viewport, hash, action_before_screenshot)
# action_before_screenshot: "open_chat" | "ask_b787" | "ask_pudong" | "ask_bms9" | "filter_topic" | None
SCENES = [
    # ---- 5 pages × responsive ----
    ("01_home_desktop",         "home",        "desktop", "",                None),
    ("02_home_tablet",          "home",        "tablet",  "",                None),
    ("03_home_mobile",          "home",        "mobile",  "",                None),
    ("04_city_desktop",         "city",        "desktop", "#B-北京大兴",      None),
    ("05_city_mobile",          "city",        "mobile",  "#B-北京大兴",      None),
    ("06_experiences_desktop",  "experiences", "desktop", "",                None),
    ("07_experience_desktop",   "experience",  "desktop", "#b787-windshield-aog", None),
    # ---- 404 ----
    ("10_404",                  "404",         "desktop", "",                None),
    # ---- Chat states ----
    ("08_chat_desktop",         "city",        "desktop", "#S-上海浦东",     "ask_pudong"),
    ("09_chat_mobile",          "city",        "mobile",  "#B-北京大兴",     "ask_b787"),
]

# Map: action -> (sugestion_text or None, post_input_text or None)
ACTIONS = {
    None:         (None,           None),
    "ask_b787":   (None,           "B787 风挡 AOG 怎么处理？"),
    "ask_pudong": (None,           "浦东 AOG 联系人？"),
    "ask_bms9":   (None,           "BMS9-3 玻璃纤维布哪里备？"),
    "open_chat":  (None,           None),
    "filter_topic": (None,         None),
}


def url_for(page, hash_=None):
    p = MOCKUP / HTML_FILES[page]
    if not p.exists():
        raise FileNotFoundError(p)
    # Use file:// URL (Tailwind CDN will still load over https)
    base = "file://" + str(p)
    if hash_:
        return f"{base}{hash_}"
    return base


def wait_for_chat_widget(page, timeout=8000):
    """Wait until the chat button is visible."""
    page.wait_for_selector("#aogChatBtn", state="visible", timeout=timeout)


def open_chat_and_ask(page, text):
    wait_for_chat_widget(page)
    page.click("#aogChatBtn")
    page.wait_for_selector("#aogChatPanel:not(.hidden)", timeout=5000)
    if text:
        # give the input a moment
        time.sleep(0.3)
        page.fill("#aogChatInput", text)
        page.press("#aogChatInput", "Enter")
        # wait for AI response (700ms in mock + buffer)
        time.sleep(1.2)


def take_screenshot(page, label, viewport, full_page=False):
    out = OUT / f"{label}.png"
    page.screenshot(path=str(out), full_page=full_page)
    sz = out.stat().st_size
    print(f"  ✓ {label}.png  ({viewport[0]}x{viewport[1]}, {sz} bytes)")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", nargs="*", help="filter scenes by label prefix")
    args = parser.parse_args()

    only = args.only
    selected = SCENES
    if only:
        selected = [s for s in SCENES if any(s[0].startswith(o) for o in only)]
        if not selected:
            print("No scenes matched --only", only)
            return 1

    print(f"==> AOG mockup screenshot: {len(selected)} scene(s)")
    print(f"    output: {OUT}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        for label, page_key, vp_name, hash_, action in selected:
            w, h = VIEWPORTS[vp_name]
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2)
            page = ctx.new_page()
            page.set_default_timeout(15000)
            url = url_for(page_key, hash_)
            print(f"  · {label}  →  {url.replace('file://','')}  ({vp_name})")
            page.goto(url, wait_until="domcontentloaded")
            # wait for Tailwind to apply + scripts to run
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except Exception:
                pass
            time.sleep(0.6)  # extra buffer for Tailwind JIT scan

            if action and action.startswith("ask_"):
                text = ACTIONS[action][1]
                open_chat_and_ask(page, text)
            elif action == "open_chat":
                open_chat_and_ask(page, None)
            elif action == "filter_topic":
                try:
                    page.click("button[data-topic='案例']")
                    time.sleep(0.3)
                except Exception:
                    pass

            take_screenshot(page, label, (w, h))
            ctx.close()

        browser.close()

    print(f"==> Done. {len(selected)} screenshot(s) in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
