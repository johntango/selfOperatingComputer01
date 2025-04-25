import os
import asyncio
import base64
import logging

import openai
from agents import Agent, Runner, function_tool, set_default_openai_key
from playwright.async_api import async_playwright, Error, TimeoutError

# ———————— Configuration ————————
API_VERSION    = "2025-03-01-preview"
MODEL          = "computer-use-preview"
DISPLAY_WIDTH  = 1024
DISPLAY_HEIGHT = 768
ITERATIONS     = 5

# ———————— Logging setup ————————
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("playwright-agent")

# ———————— Helpers ————————
async def take_screenshot(page):
    img = await page.screenshot()
    logger.info("📸 Screenshot taken")
    return base64.b64encode(img).decode("utf-8")

async def handle_action(page, action):
    """Translate a single model action into Playwright commands, with logging."""
    logger.info(f"→ Executing action: {action.type} {getattr(action, 'text', '')}{getattr(action, 'x', '')}{getattr(action, 'y', '')}")
    if action.type == "click":
        x, y = int(action.x), int(action.y)
        await page.mouse.click(x, y)
        await page.wait_for_load_state("domcontentloaded", timeout=3000)
        logger.info(f"   clicked at ({x}, {y})")
    elif action.type == "type":
        await page.keyboard.type(action.text, delay=20)
        logger.info(f"   typed '{action.text}'")
    # (Extend for scroll, keypress, etc.)

async def process_model_response(response, page):
    """Loop through the model’s computer_call outputs, execute them,
       take new screenshots, log each step, and feed back to the model."""
    for iteration in range(1, ITERATIONS + 1):
        calls = [o for o in response.output if o.type == "computer_call"]
        if not calls:
            logger.info(f"No more calls to process (after iteration {iteration-1}).")
            break

        call = calls[0]
        logger.info(f"[Iteration {iteration}] processing call_id={call.call_id}")
        await handle_action(page, call.action)

        # capture and send back
        screenshot = await take_screenshot(page)
        logger.info(f"[Iteration {iteration}] feeding screenshot back to model")
        response = openai.responses.create(
            model=MODEL,
            previous_response_id=response.id,
            tools=[{
                "type": "computer_use_preview",
                "display_width": DISPLAY_WIDTH,
                "display_height": DISPLAY_HEIGHT,
                "environment": "browser"
            }],
            input=[{
                "type": "computer_call_output",
                "call_id": call.call_id,
                "output": {
                    "type":"input_image",
                    "image_url": f"data:image/png;base64,{screenshot}"
                }
            }],
            truncation="auto"
        )
        logger.info(f"[Iteration {iteration}] received new response id={response.id}")

    return

async def main():
    api_key = os.environ.get("OPENAI_API_KEY")
    print(f"OPENAI_API_KEY {api_key}")
    set_default_openai_key(api_key)

    async with async_playwright() as p:
        logger.info("Launching headless Chromium")
        browser = await p.chromium.launch(
            headless=True,
            args=[f"--window-size={DISPLAY_WIDTH},{DISPLAY_HEIGHT}"]
        )
        context = await browser.new_context(viewport={
            "width": DISPLAY_WIDTH, "height": DISPLAY_HEIGHT
        })

        # — Attach Playwright event handlers for live logging —
        page = await context.new_page()
        page.on("console", lambda msg: logger.info(f"[Browser console] {msg.type}: {msg.text}"))
        page.on("request", lambda req: logger.info(f"[Request] {req.method} {req.url}"))
        page.on("response", lambda res: logger.info(f"[Response] {res.status} {res.url}"))

        logger.info("Starting trace (screenshots + snapshots)")
        await context.tracing.start(screenshots=True, snapshots=True)

        # 1️⃣ Navigate to a starting page
        logger.info("Navigating to https://www.bing.com")
        await page.goto("https://www.bing.com")

        # 2️⃣ Prompt the user and ask the model for the first action
        user_task = input("Enter a task (or 'exit'): ")
        if user_task.lower() == "exit":
            await browser.close()
            return

        screenshot = await take_screenshot(page)
        logger.info("→ Sending first prompt to the model")
        response =  openai.responses.create(
            model=MODEL,
            tools=[{
                "type":"computer_use_preview",
                "display_width":DISPLAY_WIDTH,
                "display_height":DISPLAY_HEIGHT,
                "environment":"browser"
            }],
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
        logger.info(f"Initial model response id={response.id}; entering action loop")

        # 3️⃣ Process the loop of actions ↔ model calls
        await process_model_response(response, page)

        # 4️⃣ Finish tracing
        logger.info("Stopping trace and saving to trace.zip")
        await context.tracing.stop(path="trace.zip")

        await browser.close()
        logger.info("Browser closed; done.")

if __name__ == "__main__":
    asyncio.run(main())
