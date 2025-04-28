from browser_use import Agent, Browser, Controller, ActionResult
from browser_use.browser.context import BrowserContext
from browser_use.browser.context import BrowserContextConfig
from langchain_openai import ChatOpenAI
from pydantic import BaseModel
import os
import uuid
from playwright.async_api import async_playwright
import asyncio

module_info = {
    'name': 'Browser-use Agent',
    'description': 'Execute a browser agent to access websites and extract information.',
    'version': '0.0.1',
    'release_date': '2025-01-01',
}


#browser = None
#browser_context = None
controller = Controller()

def exec_init():
    pass

def get_args(args=None):
    if args is not None:
        allowed_args = ['n', 'temperature', 'max_tokens', 'logprobs', 'stop', 'presence_penalty', 'frequency_penalty']
        gpt_args = dict(arg.split('=') for arg in args.gpt_args if arg in allowed_args) if args.gpt_args else {}
        if 'n' in gpt_args:
            gpt_args['n'] = int(gpt_args['n'])
            if gpt_args['n'] > 100:
                exit('n must be less than 100')
        gpt_model = args.gpt_model
        gpt_json = args.gpt_json
    else:
        gpt_args = {}
        gpt_model = 'gpt-4o-mini'
        gpt_json = True

    return {
        'gpt_args': gpt_args,
        'gpt_model': gpt_model,
        'gpt_json': gpt_json,
        '_api_key': os.getenv("OPENAI_API_KEY", "")
    }

def start_browser():

        # Caminho onde o vídeo será salvo
    output_dir = "videos"
    os.makedirs(output_dir, exist_ok=True)


    config = BrowserContextConfig(
        save_recording_path=output_dir,
        #browser_window_size={'width': 800, 'height': 600},
    )
    browser = Browser()
    browser_context = BrowserContext(browser=browser, config=config)

    return browser, browser_context

class Screenshots(BaseModel):
    # List of strings
    screenshots: list[str] = []

@controller.action(
    'Save a screenshot of the current page in PNG format',
)
async def save_screenshot(param: Screenshots, browser: BrowserContext):
    print("Saving screenshot...")
    page = await browser.get_current_page()
    screenshot = await page.screenshot(
        full_page=True,
        animations='disabled',
    )

    screenshot_folder = 'screenshots'
    os.makedirs(screenshot_folder, exist_ok=True)

    # Generate uuid
    id = str(uuid.uuid4())
    # Random file name 

    screenshot_name = f"{screenshot_folder}/screenshot_{id}.png"
    with open(screenshot_name, 'wb') as f:
        f.write(screenshot)
    print(f"Screenshot saved as {screenshot_name}")

    return ActionResult(
        extracted_content=screenshot_name
    )
    screenshots.append(screenshot_name)

async def run_agent(prompt):
    browser, browser_context = start_browser()

    agent = Agent(
        task=prompt,
        llm=ChatOpenAI(model="gpt-4.1-mini"),
        browser_context=browser_context,  # redireciona o controle do agente para essa aba com vídeo
        controller=controller,
    )

    print(f"Running agent with prompt: {prompt}")
    result = await agent.run()
    final_result = result.final_result()
    print(f"Agent result: {final_result}")


    page = await browser_context.get_current_page()
    print(page)
    print(page.video)
    video_path = await page.video.path()
    # only final name
    video_path = os.path.basename(video_path)
    print(f"Video path: {video_path}")

    await browser_context.close() 
    await browser.close() 

    screenshots = [x for x in result.extracted_content() if x.startswith('screenshots/')]

    return {
        'final_result': final_result,
        'total_input_tokens': result.total_input_tokens(),
        'video_path': video_path,
        'screenshots': screenshots,
    }
        
def exec(prompt, gpt_model, gpt_args, gpt_json, _api_key, **args):

    # Run the agent with the provided prompt
    print(f"Running agent with prompt...")
    result = asyncio.run(run_agent(prompt))
    print(f"Agent finished running.")

    # response format will mimic the response from the GPT model
    response = {
        "choices": [
            {
                "message": {
                    "content": result['final_result'],
                },
                "_extra": {
                    'video_path': result['video_path'],
                    'screenshots': result['screenshots'],
                }
            }
        ]
    }

    # TODO: calculate cost
    cost = result['total_input_tokens']/1000000.0*0.05

    return {
        'response': response,
        'cost': cost,
    }



def exec_close():
    # Close the browser context after use
    pass