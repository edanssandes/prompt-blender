import time
import random
import wx
import json

module_info = {
    'id': '66981b2d-3b8b-473a-9caf-3cd9c329f5d7',
    'name': 'Dummy',
    'description': 'Dummy execution module to mimic API return for testing purposes.',
    'version': '1.0.0',
    'release_date': '2025-07-01',
    'cache_prefix': 'dummy',
}

DEFAULT_STUB_MESSAGE = "Stub response from the dummy model."


def exec_init(gui=False):
    pass

def get_args(args=None):
    # Default value for stub_response
    if args is None:
        args = {}
    return {
        "stub_response": args.get("stub_response", DEFAULT_STUB_MESSAGE)
    }

def exec(prompt, args=None, stub_response=None):
    args = get_args(args)
    # Try to parse json. If fails, use as plain text around quotes
    try:
        parsed_stub_response = json.loads(stub_response)
        parsed_stub_response = json.dumps(parsed_stub_response, indent=2)
    except:
        parsed_stub_response = f'"{stub_response}"'

    full_stub_response = {
        "choices": [
            {
                "message": {
                    "content": parsed_stub_response
                }
            }
        ]
    }
    print("Executando o modelo dummy...")

    time.sleep(0.15)

    return {
        "response": full_stub_response,
        "cost": 0.001 + random.random() * 0.002
    }

def exec_close():
    pass

# --- ConfigPanel for GUI configuration ---
class ConfigPanel(wx.Panel):
    def __init__(self, parent, args=None):
        super().__init__(parent)
        sizer = wx.BoxSizer(wx.VERTICAL)

        lbl = wx.StaticText(self, label="Stub Response:")
        self.txt_stub_response = wx.TextCtrl(self, value=DEFAULT_STUB_MESSAGE)
        sizer.Add(lbl, flag=wx.ALL, border=5)
        sizer.Add(self.txt_stub_response, flag=wx.EXPAND | wx.ALL, border=5)

        self.SetSizer(sizer)

    @property
    def args(self):
        return {
            "stub_response": self.txt_stub_response.GetValue()
        }
    
    @args.setter
    def args(self, value):
        if value is not None:
            self.txt_stub_response.SetValue(value.get("stub_response", DEFAULT_STUB_MESSAGE))
        else:
            self.txt_stub_response.SetValue(DEFAULT_STUB_MESSAGE)


