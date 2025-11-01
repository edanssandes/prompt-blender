from groq import Groq
import os

client = None

module_info = {
    'id': '7b633c8e-697d-4761-98f9-8bbc366ab755',
    'name': 'Groq',
    'description': 'Execute Groq models via API.',
    'version': '1.0.0',
    'release_date': '2025-07-01',
    'cache_prefix': 'groq',
}

def exec_init(gui=False):
    global client
    client = Groq(api_key="")

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
        gpt_model = 'llama-3.1-70b-versatile'
        gpt_json = True

    return {
        'gpt_args': gpt_args,
        'gpt_model': gpt_model,
        'gpt_json': gpt_json,
        '_api_key': os.getenv("GROQ_API_KEY", "")
    }

def exec(prompt, gpt_model, gpt_args, gpt_json, _api_key):
    messages = []
    messages.append({"role": "user", "content": prompt})
    client.api_key = _api_key or '<null key>'

    if gpt_json:
        gpt_args['response_format'] = { "type": "json_object" }

    response = create_chat_completions(gpt_model, gpt_args, messages)

    response_dump = response.to_dict()
    cost = get_cost(response_dump)

    return {
        'response': response_dump,
        'cost': cost['cost in'] + cost['cost out'],
    }

def create_chat_completions(gpt_model, gpt_args, messages, retries=3):
    # Retry the request if it fails
    for i in range(retries):
        try:
            response = client.chat.completions.create(
                model=gpt_model,
                messages=messages,
                **gpt_args
            )
            #tokens_remaining = raw.headers.get('x-ratelimit-remaining-tokens', '')
            #requests_remaining = raw.headers.get('x-ratelimit-remaining-requests', '')
            #print(f"Tokens remaining: {tokens_remaining}, Requests remaining: {requests_remaining}")
            return response
        except Exception as e:
            if i == retries - 1:
                raise e
            print(f"Error: {e}. Retrying {i+1}/{retries}...")   
            # print full error message
            if hasattr(e, 'response') and e.response is not None:
                print(e.response.text)
            continue
    
    return response

def exec_close():
    global client
    client = None


def get_cost(response):  # FIXME duplicated code
    usage = response["usage"]

    tokens_in = usage['prompt_tokens']
    tokens_out = usage['completion_tokens']

    if response['model'] == 'gpt-3.5-turbo-0125':
        cost_in = 0.50
        cost_out = 1.50
    elif response['model'] == 'gpt-4-0125-preview':
        cost_in = 10.00
        cost_out = 30.00
    elif response['model'] == 'gpt-4o-2024-05-13':
        cost_in = 5.00
        cost_out = 15.00
    elif response['model'] == 'gpt-4o-2024-08-06':
        cost_in = 2.50
        cost_out = 10.00 
    elif response['model'] == 'gpt-manual-ui':
        cost_in = 0.00
        cost_out = 0.00
    elif response['model'] == 'gpt-4o-mini-2024-07-18':
        cost_in = 0.15
        cost_out = 0.60
    else:
        cost_in = 0.00
        cost_out = 0.00
        print(response['model'])
        
    total_cost_in = tokens_in/1000000*cost_in
    total_cost_out = tokens_out/1000000*cost_out

    return {
        'tokens in': tokens_in,
        'tokens out': tokens_out,
        'cost in': total_cost_in,
        'cost out': total_cost_out,
    }    

import wx
class ConfigPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        # Create a vertical box sizer to hold all the widgets
        vbox = wx.BoxSizer(wx.VERTICAL)

        # APIKey text box (hidden text for security reasons)
        self.apikey_label = wx.StaticText(self, label="API Key:")
        vbox.Add(self.apikey_label, flag=wx.LEFT | wx.TOP, border=5)
        self.apikey_text = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        vbox.Add(self.apikey_text, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        self.apikey_text.SetValue(os.getenv("OPENAI_API_KEY", ""))
        if self.apikey_text.GetValue() == "":
            # Set yellow background color if the API key is not set
            self.apikey_text.SetBackgroundColour(wx.Colour(255, 255, 192))


        # Model name combo box
        self.model_label = wx.StaticText(self, label="Model Name:")
        vbox.Add(self.model_label, flag=wx.LEFT | wx.TOP, border=5)
        model_choices = ["llama-3.1-70b-versatile", "llava-v1.5-7b-4096-preview", "llama-3.1-8b-instant"]  # Add more models as needed
        self.model_combo = wx.ComboBox(self, choices=model_choices, style=wx.CB_DROPDOWN)
        self.model_combo.SetValue("llama-3.1-8b-instant")  # Set the default value
        vbox.Add(self.model_combo, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

        # n selection
        self.n_label = wx.StaticText(self, label="N value:")
        vbox.Add(self.n_label, flag=wx.LEFT | wx.TOP, border=5)
        self.n_spin = wx.SpinCtrl(self, value="1", min=1, max=100)
        vbox.Add(self.n_spin, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

        # Temperature slider
        self.temperature_label = wx.StaticText(self, label="Temperature:")
        vbox.Add(self.temperature_label, flag=wx.LEFT | wx.TOP, border=5)

        self.temperature_slider = wx.Slider(self, value=100, minValue=0, maxValue=200, style=wx.SL_HORIZONTAL)
        vbox.Add(self.temperature_slider, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

        def on_temp_scroll(event):
            # Calculate the actual temperature value based on the slider position
            temp_value = self.temperature_slider.GetValue() / 100.0
            self.temperature_label.SetLabel(f"Temperature: {temp_value:.2f}")

        on_temp_scroll(None)
        self.temperature_slider.Bind(wx.EVT_SCROLL, on_temp_scroll)


        # JSON mode checkbox
        self.json_mode_checkbox = wx.CheckBox(self, label="JSON Mode")
        self.json_mode_checkbox.SetValue(True)  # Default value set to True
        vbox.Add(self.json_mode_checkbox, flag=wx.LEFT | wx.BOTTOM, border=5)

        # Set the sizer for the panel
        self.SetSizer(vbox)

        self.Fit()

    
    @property
    def args(self):
        return {
            'gpt_args': {
                'n': self.n_spin.GetValue(),
                'temperature': self.temperature_slider.GetValue() / 100,
            },
            'gpt_model': self.model_combo.GetValue(),
            'gpt_json': self.json_mode_checkbox.GetValue(),
            '_api_key': self.apikey_text.GetValue(),
        }
    
    @args.setter
    def args(self, value):

        self.model_combo.SetValue(value['gpt_model'])
        self.n_spin.SetValue(value['gpt_args'].get('n', 1))
        self.temperature_slider.SetValue(int(value['gpt_args'].get('temperature', 1) * 100))
        self.json_mode_checkbox.SetValue(value['gpt_json'])
        self.apikey_text.SetValue(value['_api_key'])
