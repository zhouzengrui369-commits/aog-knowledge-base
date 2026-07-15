#!/usr/bin/env python3
"""
AOG frontend screenshot script.
Renders all key pages at desktop / tablet / mobile widths,
and captures ChatWidget open/asked states.

Usage:
  python3 screenshot.py            # full run
  python3 screenshot.py --only home  # only specific scenes
"""
import os
import sys
import time
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

# ---------- Config ----------
ROOT = Path(__file__).resolve().parent
OUT = Path("/Users/njx/Project/AOG知识库/project/AOG知识库网站/delivery/screenshots/W1-frontend")
OUT.mkdir(parents=True, exist_ok=True)

BASE = "http://localhost:3000"

VIEWPORTS = {
    "desktop": (1280, 800),
    "tablet":  (768, 1024),
    "mobile":  (360, 640),
}

# Map scene -> url path
ROUTES = {
    "home":        "/",
    "city":        "/city/B-北京大兴",      # URL-encoded path
    "city-pudong": "/city/S-上海浦东",
    "city-hkg":    "/city/H-香港",
    "experiences": "/experiences",
    "experience":  "/experience/b787-windshield-aog",
    "experience-workflow": "/experience/aog-workflow-r1",
    "404":         "/nonexistent-path",
}

# Scene definitions: (label, route_key, viewport, action)
# action: None | "open_chat" | "ask_b787" | "ask_pudong" | "ask_bms9" | "filter_案例" | "tab_contacts" | "tab_parts"
SCENES = [
    # ---- 5 pages × responsive (home / city / experiences / experience / 404) ----
    ("01_home_desktop",            "home",        "desktop", None),
    ("02_home_tablet",             "home",        "tablet",  None),
    ("03_home_mobile",             "home",        "mobile",  None),
    ("04_city_desktop",            "city",        "desktop", None),
    ("05_city_mobile",             "city",        "mobile",  None),
    ("06_city_pudong",             "city-pudong", "desktop", None),
    ("07_city_hkg",                "city-hkg",    "desktop", None),
    ("08_experiences_desktop",     "experiences", "desktop", None),
    ("09_experiences_mobile",      "experiences", "mobile",  None),
    ("10_experience_desktop",      "experience",  "desktop", None),
    ("11_experience_workflow",     "experience-workflow", "desktop", None),
    # ---- 404 ----
    ("12_404",                     "404",         "desktop", None),
    # ---- ChatWidget 状态 ----
    ("13_chat_desktop_open",       "city-pudong", "desktop", "open_chat"),
    ("14_chat_desktop_ask",        "city-pudong", "desktop", "ask_pudong"),
    ("15_chat_mobile_ask",         "city",        "mobile",  "ask_b787"),
    # ---- 交互（tab + filter） ----
    ("16_city_tab_parts",          "city",        "desktop", "tab_parts"),
    ("17_city_tab_contacts",       "city",        "desktop", "tab_contacts"),
    ("18_experiences_filter",      "experiences", "desktop", "filter_案例"),
]


def url_for(route_key: str) -> str:
    path = ROUTES.get(route_key)
    if not path:
        raise ValueError(f"Unknown route: {route_key}")
    return f"{BASE}{path}"


def open_chat_and_ask(page, text):
    """打开 ChatWidget 浮窗 + 输入问题"""
    # 等待浮动按钮
    page.wait_for_selector('button[aria-label="打开 AI 助手"]', state="visible", timeout=10000)
    page.click('button[aria-label="打开 AI 助手"]')
    # 等待对话框（role=dialog）
    page.wait_for_selector('[role="dialog"][aria-label="AOG AI 助手"]', state="visible", timeout=5000)
    if text:
        time.sleep(0.3)
        # 找到输入框（dialog 内的 input[type="text"]）
        page.fill('[role="dialog"] input[type="text"]', text)
        page.press('[role="dialog"] input[type="text"]', "Enter")
        # 等 AI 响应（默认 mock 700ms + buffer；后端未启动时 fast-fail）
        time.sleep(1.5)


def take_screenshot(page, label, viewport, full_page=False):
    out = OUT / f"{label}.png"
    page.screenshot(path=str(out), full_page=full_page)
    sz = out.stat().st_size
    print(f"  ✓ {label}.png  ({viewport[0]}x{viewport[1]}, {sz} bytes)")


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

    print(f"==> AOG frontend screenshot: {len(selected)} scene(s)")
    print(f"    base: {BASE}")
    print(f"    output: {OUT}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()

        for label, route_key, vp_name, action in selected:
            w, h = VIEWPORTS[vp_name]
            ctx = browser.new_context(viewport={"width": w, "height": h}, device_scale_factor=2)
            page = ctx.new_page()
            page.set_default_timeout(15000)
            url = url_for(route_key)
            print(f"  · {label}  →  {url}  ({vp_name})")
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=15000)
                # wait for Next.js hydration + Tailwind compile
                try:
                    page.wait_for_load_state("networkidle", timeout=4000)
                except Exception:
                    pass
                time.sleep(0.5)

                if action == "open_chat":
                    open_chat_and_ask(page, None)
                elif action == "ask_b787":
                    open_chat_and_ask(page, "B787 风挡 AOG 怎么处理？")
                elif action == "ask_pudong":
                    open_chat_and_ask(page, "浦东 AOG 联系人？")
                elif action == "ask_bms9":
                    open_chat_and_ask(page, "BMS9-3 玻璃纤维布哪里备？")
                elif action == "tab_parts":
                    page.click("button:has-text('备件清单')")
                    time.sleep(0.4)
                elif action == "tab_contacts":
                    page.click("button:has-text('联系人')")
                    time.sleep(0.4)
                elif action == "filter_案例":
                    page.click("button:has-text('案例')")
                    time.sleep(0.4)

                take_screenshot(page, label, (w, h))
            except Exception as e:
                print(f"  ✗ {label} FAILED: {e}")
            finally:
                ctx.close()

        browser.close()

    print(f"==> Done. {len(selected)} screenshot(s) attempted in {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
