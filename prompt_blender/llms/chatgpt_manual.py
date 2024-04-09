import pyperclip
from datetime import datetime

def exec_init(gpt_api_key_file):
    pass


def exec(prompt, gpt_model, gpt_args, gpt_json=False):
    print('-'*50)
    print(prompt)
    print('-'*50)

    # Copy the prompt to the clipboard
    pyperclip.copy(prompt)

    # Wait for a input to simulate the OpenAI ChatGPT UI response
    response = input('Paste the prompt in the ChatGPT UI and copy back the response here:\n')

    # Generate The Unix timestamp (in seconds) of when the chat completion was created
    timestamp = datetime.now().strftime('%s')

    # Mimic the OpenAI ChatGPT response
    response_dump = {
        "id": None,
        "choices": [
            {
                "message": {
                    "content": response,
                    "role": "assistant", 
                    "function_call": None,
                    "tool_calls": None,
                }
            }
        ], 
        "created": timestamp,
        "model": "gpt-manual-ui",
        "object": "chat.completion",
        "usage": {"completion_tokens": 0, "prompt_tokens": 0, "total_tokens": 0},
    }
    
    
    return response_dump

def exec_close():
    pass

        
