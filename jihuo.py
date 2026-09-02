import asyncio
import re
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# 需要保活的 Streamlit 网址列表
urls = [
    "https://shenzhenmodel-9ihnhaceacjjxieza3wapz.streamlit.app/"
]

async def visit(url):
    async with async_playwright() as p:
        # 启动 Chromium 并规避自动化特征
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled"
            ]
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        try:
            print(f"正在访问: {url}")
            
            # 【关键修复 1】: 将 networkidle 改为 domcontentloaded。
            # 避免被 Streamlit 的 WebSocket 长连接拖延导致超时崩溃。
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # 定位唤醒按钮 (匹配 Streamlit 默认的 "Yes, get this app back up!" 文案)
            wake_button = page.locator("button", has_text=re.compile(r"get this app back up|wake up", re.IGNORECASE))

            try:
                # 【优化】: 只需要等 10 秒。如果 10 秒还没出现唤醒按钮，说明 APP 处于活跃状态，没有休眠。
                await wake_button.wait_for(state="visible", timeout=10000)
                print(f"检测到休眠状态，正在尝试点击唤醒: {url}")
                
                # 强制点击唤醒按钮
                await wake_button.click(force=True)
                print("点击成功，正在等待 Streamlit 容器冷启动 (云端分配资源约需 30-60 秒)...")
                
                # 【关键修复 2】: 点击后，通过检测 Streamlit 的主容器类名 `.stApp` 来判断应用是否真的启动成功了
                try:
                    # 等待 Streamlit 的应用主界面出现，给予 60 秒的冷启动容忍时间
                    await page.wait_for_selector('.stApp, [data-testid="stAppViewContainer"]', timeout=60000)
                    print(f"✅ 唤醒请求已完成，应用页面已成功加载: {url}")
                except PlaywrightTimeoutError:
                    print(f"⚠️ 唤醒按钮已点击，但在 60 秒内未检测到应用界面完全展开，可能还在启动中: {url}")

            except PlaywrightTimeoutError:
                # 找不到按钮，说明没在休眠
                print(f"✅ 网页中未检测到休眠按钮，应用正处于正常活跃状态: {url}")

        except Exception as e:
            print(f"⚠️ 处理该网址时发生异常 [{url}]: {e}")
        finally:
            await context.close()
            await browser.close()

async def main():
    for target_url in urls:
        await visit(target_url)

if __name__ == "__main__":
    asyncio.run(main())