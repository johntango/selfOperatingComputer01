import os, asyncio, base64
import openai 

from agents import Agent, Runner, function_tool,set_default_openai_key
from playwright.async_api import async_playwright, Error


api_key = os.environ.get("OPENAI_API_KEY")
print(f"OPENAI_API_KEY {api_key}")
set_default_openai_key(api_key)
# setup openai client
client = 



from playwright.async_api import Browser, Page, Playwright, async_playwright,TimeoutError
# Configuration
API_VERSION    = "2025-03-01-preview"
MODEL          = "computer-use-preview"
DISPLAY_WIDTH  = 1024
DISPLAY_HEIGHT = 768
ITERATIONS     = 5

# Initialize OpenAI client (Azure)
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)
"""client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    azure_ad_token_provider=token_provider,
    api_version=API_VERSION
)"""

async def take_screenshot(page):
    img = await page.screenshot()
    return base64.b64encode(img).decode("utf-8")

async def handle_action(page, action):
    """Translate a single model action into Playwright commands."""
    if action.type == "click":
        x, y = int(action.x), int(action.y)
        await page.mouse.click(x, y)
        await page.wait_for_load_state("domcontentloaded", timeout=3000)
    elif action.type == "type":
        await page.keyboard.type(action.text, delay=20)
    # (Implement other action types: scroll, keypress, etc.)

async def process_model_response(response, page):
    """Loop through model’s `computer_call` outputs, execute them, 
       take new screenshots, and feed back to the model."""
    for _ in range(ITERATIONS):
        calls = [o for o in response.output if o.type == "computer_call"]
        if not calls:
            break
        call = calls[0]
        await handle_action(page, call.action)
        screenshot = await take_screenshot(page)
        response = client.responses.create(
            model=MODEL,
            previous_response_id=response.id,
            tools=[{"type":"computer_use_preview",
                    "display_width":DISPLAY_WIDTH,
                    "display_height":DISPLAY_HEIGHT,
                    "environment":"browser"}],
            input=[{
                "type":"computer_call_output",
                "call_id": call.call_id,
                "output": {
                    "type":"input_image",
                    "image_url": f"data:image/png;base64,{screenshot}"
                }
            }],
            truncation="auto"
        )
    return

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False,
                                         args=[f"--window-size={DISPLAY_WIDTH},{DISPLAY_HEIGHT}"])
        page = await browser.new_page(viewport={"width":DISPLAY_WIDTH,"height":DISPLAY_HEIGHT})
        await page.goto("https://www.bing.com")
        user_task = input("Enter a task (or 'exit'): ")
        if user_task.lower() == "exit":
            return

        screenshot = await take_screenshot(page)
        response = openai.responses.create(
            model=MODEL,
            tools=[{"type":"computer_use_preview",
                    "display_width":DISPLAY_WIDTH,
                    "display_height":DISPLAY_HEIGHT,
                    "environment":"browser"}],
            instructions=(
                "You are an AI agent controlling a browser via Playwright. "
                "After each action, take a screenshot to verify success. "
                "When done, return control."
            ),
            input=[{
                "role":"user",
                "content":[
                    {"type":"input_text","text": user_task},
                    {"type":"input_image","image_url": f"data:image/png;base64,{screenshot}"}
                ]
            }],
            reasoning={"generate_summary":"concise"},
            truncation="auto"
        )
        await process_model_response(response, page)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
