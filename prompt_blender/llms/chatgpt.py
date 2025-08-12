from openai import OpenAI
import os
import io
import json
import wx

client = None

MODULE_UUID = 'b85680ef-8da2-4ed5-b881-ce33fe5d3ec0'

module_info = {
    'id': MODULE_UUID,
    'name': 'ChatGPT',
    'description': 'Execute OpenAI models via API.',
    'version': '1.0.0',
    'release_date': '2025-07-01',
    'cache_prefix': 'openai',
}


DEFAULT_MODEL = 'gpt-4.1-mini'

def exec_init():
    global client
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

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
        batch_mode = args.batch_mode
    else:
        gpt_args = {}
        gpt_model = DEFAULT_MODEL
        gpt_json = True
        batch_mode = False

    return {
        'gpt_args': gpt_args,
        'gpt_model': gpt_model,
        'gpt_json': gpt_json,
        #'_api_key': os.getenv("OPENAI_API_KEY", "")
        'batch_mode': batch_mode,
    }


def exec(prompt, gpt_model, gpt_args, gpt_json, batch_mode):
    messages = []
    messages.append({"role": "user", "content": prompt})

    if client.api_key is None or client.api_key == '':
        dlg = wx.TextEntryDialog(None, "Please enter your OpenAI API key:", "OpenAI API Key", "")
        dlg.ShowModal()
        result = dlg.GetValue()
        dlg.Destroy()
        
        client.api_key = result

    if gpt_json:
        gpt_args['response_format'] = { "type": "json_object" }

    if '-search' in gpt_model:
        gpt_args['web_search_options'] = {
            'user_location': {
                'type': "approximate",
                'approximate': {
                    'country': "BR"
                },
            },            
        }
        print(f"Using web search for {gpt_model}")
        if 'temperature' in gpt_args:
            del gpt_args['temperature']
        if 'n' in gpt_args:
            del gpt_args['n']
        if 'response_format' in gpt_args:
            del gpt_args['response_format']

    if batch_mode:
        return {
            'delayed': {
                "body": {
                    "model": gpt_model,
                    "messages": messages,
                    **gpt_args
                }
            }
        }

    response = client.chat.completions.create(
        model=gpt_model,
        messages=messages,
        **gpt_args
    )

    response_dump = response.to_dict()
    cost = get_cost(response_dump)

    return {
        'response': response_dump,
        'cost': cost['cost in'] + cost['cost out'],
    }


def exec_delayed(delayed_content: dict):
    print("TESTE")
    jsonl_file_content = []
    batch_ids = set()
    #return

    for key, content in delayed_content.items():
        print(key, content)
        if "body" in content:
            jsonl_file_content.append({
                "custom_id": key,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": content["body"]
            })
        if "batch_id" in content:
            batch_ids.add(content["batch_id"])

    new_delayed_content = {}

    for batch_id in batch_ids:
        batch = client.batches.retrieve(batch_id)
        print(batch)
        if batch.status != "completed":
            print(f"Batch {batch_id} is not completed yet.")
        elif batch.output_file_id is None and batch.error_file_id is not None:
            print(f"Batch {batch_id} has errors.")
            error_response = client.files.content(batch.error_file_id)
            error_data = error_response.text
            print(error_data)
            for line in error_data.splitlines():
                response_dump = json.loads(line)
                response = response_dump['response']['body']
                custom_id = response_dump['custom_id']
                new_delayed_content[custom_id] = {
                    'response': response,
                    'error': response['error']['type'],
                    'batch_id': batch_id,
                }
            # Delete the batch input file because we don't need it anymore
            client.files.delete(batch.input_file_id)
            client.files.delete(batch.error_file_id)
        else:
            # Retrieve the file content
            print(batch.output_file_id)
            file_response = client.files.content(batch.output_file_id)
            jsonl_data = file_response.text
            print(jsonl_data)
            first_result = True
            for line in jsonl_data.splitlines():
                response_dump = json.loads(line)
                response = response_dump['response']['body']
                custom_id = response_dump['custom_id']
                cost = get_cost(response)

                new_delayed_content[custom_id] = {
                    'response': response,
                    'cost': (cost['cost in'] + cost['cost out'])*0.5,  # 50% discount for batch processing
                    'batch_id': batch_id,
                }

                if first_result:
                    # Include full elapsed time for the batch in the first response only
                    elapsed_time = batch.completed_at - batch.created_at
                    new_delayed_content[custom_id]['elapsed_time'] = elapsed_time
                    first_result = False

            # Delete the batch input file because we don't need it anymore
            client.files.delete(batch.input_file_id)

    if jsonl_file_content:
        show_batch_warning(jsonl_file_content)
        
        # Create a JSONL file-like object
        jsonl_str = '\n'.join([json.dumps(item) for item in jsonl_file_content])
        jsonl_file_io = io.BytesIO(jsonl_str.encode("utf-8")) 


        batch_input_file = client.files.create(
            file=jsonl_file_io,
            purpose="batch"
        )
        print(batch_input_file)
        batch_input_file_id = batch_input_file.id

        batch_object = client.batches.create(
            input_file_id=batch_input_file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={
                "description": "prompt-blender job"
            }
        )
        print(batch_object)

        for key in delayed_content.keys():
            new_delayed_content[key] = {'delayed': {'batch_id': batch_object.id}}

    return new_delayed_content

def exec_close():
    global client
    client = None

def show_batch_warning(jsonl_file_content):
    # Ask Continue or Abort
    msg = "Batch processing is experimental and the cost of the batch cannot be tracked.\n\nDo you want to continue?"
    dlg = wx.MessageDialog(None, msg, f"Batch Processing Warning - {len(jsonl_file_content)} item(s)", wx.YES_NO | wx.ICON_WARNING)
    result = dlg.ShowModal()
    dlg.Destroy()
    if result == wx.ID_NO:
        raise Exception("Batch processing aborted by user.")
    

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
    elif response['model'] == 'gpt-4o-mini-search-preview':
        cost_in = 0.15
        cost_out = 0.60 
    elif response['model'] == 'gpt-4.1-nano-2025-04-14':
        cost_in = 0.10
        cost_out = 0.40
    elif response['model'] == 'gpt-4.1-mini-2025-04-14':
        cost_in = 0.40
        cost_out = 1.60
    elif response['model'] == 'gpt-5-mini-2025-08-07':
        cost_in = 0.25
        cost_out = 2.00        
    else:
        cost_in = 0
        cost_out = 0
        
    total_cost_in = tokens_in/1000000*cost_in
    total_cost_out = tokens_out/1000000*cost_out

    return {
        'tokens in': tokens_in,
        'tokens out': tokens_out,
        'cost in': total_cost_in,
        'cost out': total_cost_out,
    }    

class ConfigPanel(wx.Panel):
    def __init__(self, parent):
        super().__init__(parent)

        # Create a vertical box sizer to hold all the widgets
        vbox = wx.BoxSizer(wx.VERTICAL)

        # # APIKey text box (hidden text for security reasons)
        # self.apikey_label = wx.StaticText(self, label="API Key:")
        # vbox.Add(self.apikey_label, flag=wx.LEFT | wx.TOP, border=5)
        # self.apikey_text = wx.TextCtrl(self, style=wx.TE_PASSWORD)
        # vbox.Add(self.apikey_text, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)
        # self.apikey_text.SetValue(os.getenv("OPENAI_API_KEY", ""))
        # if self.apikey_text.GetValue() == "":
        #     # Set yellow background color if the API key is not set
        #     self.apikey_text.SetBackgroundColour(wx.Colour(255, 255, 192))


        # Model name combo box
        self.model_label = wx.StaticText(self, label="Model Name:")
        vbox.Add(self.model_label, flag=wx.LEFT | wx.TOP, border=5)
        model_choices = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo", "gpt-4o-mini-search-preview", "gpt-4.1-nano", "gpt-4.1-mini", "gpt-5-mini", "gpt-5-nano"]  # Add more models as needed
        self.model_combo = wx.ComboBox(self, choices=model_choices, style=wx.CB_DROPDOWN)
        self.model_combo.SetValue(DEFAULT_MODEL)  # Set the default value
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

        self.on_temp_scroll(None)
        self.temperature_slider.Bind(wx.EVT_SCROLL, self.on_temp_scroll)

        # JSON mode checkbox
        self.json_mode_checkbox = wx.CheckBox(self, label="JSON Mode")
        self.json_mode_checkbox.SetValue(True)  # Default value set to True
        vbox.Add(self.json_mode_checkbox, flag=wx.LEFT | wx.BOTTOM, border=5)

        # Batch mode checkbox
        self.batch_mode_checkbox = wx.CheckBox(self, label="Batch Mode (experimental)")
        self.batch_mode_checkbox.SetValue(False)  # Default value set to False
        vbox.Add(self.batch_mode_checkbox, flag=wx.LEFT | wx.BOTTOM, border=5)

        # Set the sizer for the panel
        self.SetSizer(vbox)

        self.Fit()

    def on_temp_scroll(self, event):
        # Calculate the actual temperature value based on the slider position
        temp_value = self.temperature_slider.GetValue() / 100.0
        self.temperature_label.SetLabel(f"Temperature: {temp_value:.2f}")

    
    @property
    def args(self):
        return {
            'gpt_args': {
                'n': self.n_spin.GetValue(),
                'temperature': self.temperature_slider.GetValue() / 100,
            },
            'gpt_model': self.model_combo.GetValue(),
            'gpt_json': self.json_mode_checkbox.GetValue(),
            #'_api_key': self.apikey_text.GetValue(),
            'batch_mode': self.batch_mode_checkbox.GetValue(),
        }
    
    @args.setter
    def args(self, value):

        self.model_combo.SetValue(value['gpt_model'])
        self.n_spin.SetValue(value['gpt_args'].get('n', 1))
        temperature = int(value['gpt_args'].get('temperature', 1) * 100)
        self.temperature_slider.SetValue(temperature)
        self.on_temp_scroll(None)
        #self.temperature_label.SetLabel(f"Temperature: {temperature / 100:.2f}")
        self.json_mode_checkbox.SetValue(value['gpt_json'])
        #self.apikey_text.SetValue(value['_api_key'])
        self.batch_mode_checkbox.SetValue(value.get('batch_mode', False))

