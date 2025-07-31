import os
# Disable telemetry before importing browser_use
os.environ["ANONYMIZED_TELEMETRY"] = "false"

from browser_use import Agent, Browser, Controller, ActionResult
from browser_use.browser.context import BrowserContext
from browser_use.browser.context import BrowserContextConfig
from langchain_openai import ChatOpenAI
from langchain_community.callbacks.manager import get_openai_callback
from pydantic import BaseModel
import os
import re
import uuid
from playwright.async_api import async_playwright
import asyncio
import json

from prompt_blender.analysis.gpt_json import extract_json


module_info = {
    'id': 'a95f8287-6a34-4ecb-b917-dd994476f386',
    'name': 'Browser-use Agent',
    'description': 'Execute a browser agent to access websites and extract information.',
    'version': '0.0.1',
    'release_date': '2025-01-01',
    'cache_prefix': 'browser_use',
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
        permissions=[]  # Avoid browser permission prompts
        #browser_window_size={'width': 800, 'height': 600},
    )
    browser = Browser()
    browser_context = BrowserContext(browser=browser, config=config)

    return browser, browser_context

@controller.action(
    'Save a screenshot of the current page in PNG format',
)
async def save_screenshot(title: str, browser: BrowserContext):
    print("Saving screenshot...", title)
    page = await browser.get_current_page()
    screenshot = await page.screenshot(
        full_page=True,
        animations='disabled',
    )
    browser.take_screenshot(screenshot)

    screenshot_folder = 'screenshots'
    os.makedirs(screenshot_folder, exist_ok=True)

    # Generate uuid
    id = str(uuid.uuid4())
    # Random file name 

    # Sanitize title. Accept only numbers, letters. Replace anything else with '_'
    title = re.sub(r'[^a-zA-Z0-9]', '_', title) if title else '_'

    screenshot_name = f"{screenshot_folder}/screenshot_{title}_{id}.png"
    with open(screenshot_name, 'wb') as f:
        f.write(screenshot)
    print(f"Screenshot saved as {screenshot_name}")

    screenshot_filename = f"{screenshot_folder}/screenshot_{title}_{id}.info"
    with open(screenshot_filename, 'w') as f:
        f.write(f"{page.url}\n")

    return ActionResult(
        extracted_content=screenshot_name
    )

@controller.action(
    'Store the final result in JSON format',
)
async def store_final_result_json(json_data: str):
    try:
        data = extract_json(json_data)
        json_str = json.dumps(data, indent=4)
        print(f"Storing final result as JSON: {json_str}")
        return ActionResult(
            success=True,
            is_done=True,
            extracted_content=json_str
        )
    except ValueError as e:
        return ActionResult(
            error=f"Failed to parse JSON: {str(e)}"
        )



async def run_agent(prompt):
    browser, browser_context = start_browser()

    llm = ChatOpenAI(model="gpt-4.1-mini")
    #llm = ChatOpenAI(model="gpt-4.1-nano")

    agent = Agent(
        task=prompt,
        llm=llm,
        browser_context=browser_context,  # redireciona o controle do agente para essa aba com vídeo
        controller=controller,
    )

    print(f"Running agent with prompt: {prompt}")
    with get_openai_callback() as cb:    
        result = await agent.run()
        final_result = result.final_result()
        print(f"Agent result: {final_result}")
        print(cb)
        input_tokens = cb.prompt_tokens
        output_tokens = cb.completion_tokens
        total_tokens = cb.total_tokens
        cost = cb.total_cost


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
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'total_tokens': total_tokens,
        'cost': cost,
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

    cost = result['cost']

    return {
        'response': response,
        'cost': cost,
    }



def exec_close():
    # Close the browser context after use
    pass