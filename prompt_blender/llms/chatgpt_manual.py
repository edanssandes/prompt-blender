import wx
import time
import pyperclip
from datetime import datetime

use_ui = False
have_result = False

def exec_init():
    global use_ui
    use_ui = wx.App.IsMainLoopRunning()
    if not use_ui:
        print('The ChatGPT Manual UI requires a running wxPython GUI environment.')
        print('Please run the GUI to use this feature.')


def get_args(args=None):
    return {}

def show_ui_message(prompt):
    global haveResult
    #wx.MessageBox(prompt, 'ChatGPT Manual UI', wx.OK | wx.ICON_INFORMATION)

    # Show a dialog to ask for the response in json format
    #app = wx.App(False)
    dialog = wx.TextEntryDialog(None, prompt, 'ChatGPT Manual UI')
    if dialog.ShowModal() == wx.ID_OK:
        haveResult = dialog.GetValue()
    else:
        haveResult = False

    #haveResult = True

def exec(prompt):
    global haveResult

    if use_ui:
        haveResult = None
        wx.CallAfter(show_ui_message, prompt)
        while haveResult is None: time.sleep(0.5)

        response = haveResult
    else:
        print('-'*50)
        print(prompt)
        print('-'*50)
        
        # Copy the prompt to the clipboard
        pyperclip.copy(prompt)

        # Wait for a input to simulate the OpenAI ChatGPT UI response
        response = input('Paste the prompt in the ChatGPT UI and copy back the response here:\n')




    # Generate The Unix timestamp (in seconds) of when the chat completion was created
    timestamp = int(datetime.now().timestamp())

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
    
    
    return {
        'response': response_dump,
        'cost': 0,
    }

def exec_close():
    pass

        
