from agents import Agent, Runner, function_tool
import os
from playwright.async_api import async_playwright, Error
from agents import set_default_openai_key

api_key = os.environ.get("OPENAI_API_KEY")
print(f"OPENAI_API_KEY {api_key}")
set_default_openai_key(api_key)

@function_tool
async def capture_screenshot(url: str) -> str:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(viewport={"width": 1920, "height": 1080})
            page = await context.new_page()
            await page.goto(url)
            screenshot_path = "webpage_screenshot.png"
            await page.screenshot(path=screenshot_path, full_page=True)
            await browser.close()

        return os.path.abspath(screenshot_path)
    except Error as e:
        return f"Playwright Error: {e}"
    except Exception as e:
        return f"General Error: {e}"

@function_tool
def list_current_directory_files() -> list:
    return os.listdir('.')

agent = Agent(
      name="Computer Use Agent",
    tools=[capture_screenshot, list_current_directory_files],
)

import asyncio

async def main():
    result = await Runner.run(agent, input="Capture a screenshot of 'https://example.com' and list all files in the current directory.")
    print("Agent Output:", result.final_output)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
