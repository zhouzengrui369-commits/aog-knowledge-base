"""
Sprint C 验证脚本 — 5 张 Playwright 截图
- 01_airlines_list.png — 航司列表页
- 02_airline_detail_CA.png — 国航详情
- 03_search_donghang.png — 搜"东航"结果
- 04_alphabet_sidebar.png — 字母 sidebar 切到 "航司" tab
- 05_city_hub_link.png — 航司详情里的基地城市链接能跳 city detail
"""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("/tmp/aog_sprint_c_verify")
OUT.mkdir(parents=True, exist_ok=True)

BASE = os.environ.get("AOG_BASE", "http://localhost:3002")

def shot(page, name):
    p = OUT / f"{name}.png"
    page.screenshot(path=str(p), full_page=True)
    print(f"  ✓ {p}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        page = ctx.new_page()

        # 1. 航司列表页
        print("[1/5] 航司列表页 ...")
        page.goto(f"{BASE}/airlines", wait_until="networkidle", timeout=30000)
        # 等数据 fetch
        time.sleep(2)
        # 等卡片渲染 (load → fetch → setAirlines → render)
        page.wait_for_selector("a[href*='/airlines/']", timeout=15000)
        shot(page, "01_airlines_list")

        # 2. 国航详情
        print("[2/5] 国航详情 ...")
        page.goto(f"{BASE}/airlines/CA", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        # 等数据
        page.wait_for_selector("h1", timeout=10000)
        # 确保出现 "中国国际航空"
        page.wait_for_function(
            "() => document.body.innerText.includes('中国国际航空')",
            timeout=15000,
        )
        shot(page, "02_airline_detail_CA")

        # 3. 搜"东航"
        print("[3/5] 搜'东航' ...")
        page.goto(f"{BASE}/airlines", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        # 等 input 出现
        page.wait_for_selector("input[type='search']", timeout=10000)
        page.fill("input[type='search']", "东航")
        time.sleep(1.5)  # 等待 React filter
        shot(page, "03_search_donghang")

        # 4. 字母 sidebar 切到 "航司" tab
        print("[4/5] 字母 sidebar 切到航司 tab ...")
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        # 等 AlphabetNav 加载
        # tab 按钮包含 "航司" 文本 (role=tab)
        airline_tab = page.get_by_role("tab", name="航司", exact=False)
        if airline_tab.count() == 0:
            # fallback: 找 button with text
            airline_tab = page.locator("button:has-text('航司')").first
        try:
            airline_tab.click(timeout=5000)
            time.sleep(1)
            # 点 C 字母
            c_letter = page.locator("button:has-text('C')").first
            if c_letter.count() == 0:
                # 在 sidebar 内找
                c_letter = page.locator("[role='tablist'] ~ * button:has-text('C')").first
            c_letter.click(timeout=5000)
            time.sleep(1)
        except Exception as e:
            print(f"  WARN: tab/letter click failed: {e}")
        shot(page, "04_alphabet_sidebar")

        # 5. 基地城市链接 → city detail
        print("[5/5] 基地城市链接 → city detail ...")
        page.goto(f"{BASE}/airlines/CZ", wait_until="networkidle", timeout=30000)
        time.sleep(2)
        # 等数据
        page.wait_for_function(
            "() => document.body.innerText.includes('中国南方航空')",
            timeout=15000,
        )
        # 找 hub 链接 (city 存在才显示)
        # CZ 有 G-广州 hub, 该 city 存在 → 应有 /city/G-广州 链接
        guangzhou_link = page.locator("a[href*='/city/']").first
        if guangzhou_link.count() == 0:
            print("  WARN: 找不到 city hub 链接, 试 MF 厦门")
            page.goto(f"{BASE}/airlines/MF", wait_until="networkidle", timeout=30000)
            time.sleep(2)
        else:
            # 截图当前页 + 点击后页面
            shot(page, "05a_airline_with_hub_link")
            guangzhou_link.click()
            time.sleep(3)
            shot(page, "05_city_hub_link")
            print(f"  跳到: {page.url}")

        browser.close()
        print("---")
        print(f"所有截图存到 {OUT}")
        for f in sorted(OUT.glob("*.png")):
            print(f"  - {f.name}  ({f.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
