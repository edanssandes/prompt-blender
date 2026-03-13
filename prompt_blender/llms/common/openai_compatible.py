from openai import OpenAI
import os
import re
import io
import json
import wx
import threading

from prompt_blender.analysis.gpt_cost import analyse as get_cost
_gui = False

class OpenAICompatibleModule:
    def __init__(self, 
                 base_url=None,
                 models=None,
                 default_model=None,
                 environment_var=None,
                 id=None,
                 name=None,
                 description=None,
                 version=None,
                 release_date=None,
                 cache_prefix=None):
        self.base_url = base_url
        self.models = models
        self.default_model = default_model
        self.environment_var = environment_var

        self._module_info = None
        if id is not None:
            self._module_info = {
                'id': id,
                'name': name,
                'description': description,
                'version': version or '',
                'release_date': release_date,
                'cache_prefix': cache_prefix,
            }

        self._gui = False
        self.client = None

    @property
    def module_info(self):
        return self._module_info

    def exec_init(self, gui=False):
        self.client = None
        self._gui = gui

    def exec(self, prompt, gpt_model, gpt_args, gpt_json, batch_mode, web_search):
        if self.client is None:
            self.client = _create_client(self.base_url, self.environment_var, gui=self._gui)

        return _exec_compatible(prompt, gpt_model, gpt_args, gpt_json, batch_mode, web_search, client=self.client)

    def exec_delayed(self, delayed_content: dict):
        return exec_delayed_compatible(delayed_content, self.client)

    def exec_close(self):
        self.client = None

    def get_args(self, args=None):
        return get_args_compatible(args=args, default_model=self.default_model)
    
    def ConfigPanel(self, parent):
        return self._ConfigPanel(parent, self.models, self.default_model)    

    class _ConfigPanel(wx.Panel):
        def __init__(self, parent, list_models, default_model):
            super().__init__(parent)

            # Create a vertical box sizer to hold all the widgets
            vbox = wx.BoxSizer(wx.VERTICAL)

            # Model name combo box
            self.model_label = wx.StaticText(self, label="Model Name:")
            vbox.Add(self.model_label, flag=wx.LEFT | wx.TOP, border=5)
            self.model_combo = wx.ComboBox(self, choices=[], style=wx.CB_DROPDOWN)
            vbox.Add(self.model_combo, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=5)

            # Populate models for the default base API
            self._update_model_list(list_models, default_model)

            # Bind event for model change
            self.model_combo.Bind(wx.EVT_COMBOBOX, self.on_model_change)

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

            # Web search checkbox
            self.web_search_checkbox = wx.CheckBox(self, label="Enable Web Search (experimental)")
            self.web_search_checkbox.SetValue(False)  # Default value set to False
            vbox.Add(self.web_search_checkbox, flag=wx.LEFT | wx.BOTTOM, border=5)

            # Batch mode checkbox
            self.batch_mode_checkbox = wx.CheckBox(self, label="Batch Mode (experimental)")
            self.batch_mode_checkbox.SetValue(False)  # Default value set to False
            vbox.Add(self.batch_mode_checkbox, flag=wx.LEFT | wx.BOTTOM, border=5)

            # Set the sizer for the panel
            self.SetSizer(vbox)

            self.Fit()

            # Initialize checkbox states based on default model
            self.on_model_change(None)


        def on_temp_scroll(self, event):
            # Calculate the actual temperature value based on the slider position
            temp_value = self.temperature_slider.GetValue() / 100.0
            self.temperature_label.SetLabel(f"Temperature: {temp_value:.2f}")

        def on_model_change(self, event):
            model = self.model_combo.GetValue()
            if "-search" in model:
                self.web_search_checkbox.Enable(False)
                self.json_mode_checkbox.Enable(False)
            else:
                self.web_search_checkbox.Enable(True)
                self.json_mode_checkbox.Enable(True)

        def _update_model_list(self, models, default_model):
            """Update the model combo box based on the selected Base API."""
            self.model_combo.Clear()
            for model in models:
                self.model_combo.Append(model)
            self.model_combo.SetValue(default_model)
        
        @property
        def args(self):
            return {
                'gpt_args': {
                    'n': self.n_spin.GetValue(),
                    'temperature': self.temperature_slider.GetValue() / 100,
                },
                'gpt_model': self.model_combo.GetValue(),
                'gpt_json': self.json_mode_checkbox.GetValue(),
                'web_search': self.web_search_checkbox.GetValue(),
                'batch_mode': self.batch_mode_checkbox.GetValue(),
            }
        
        @args.setter
        def args(self, value):
            self.model_combo.SetValue(value['gpt_model'])
            self.n_spin.SetValue(value['gpt_args'].get('n', 1))
            temperature = int(value['gpt_args'].get('temperature', 1) * 100)
            self.temperature_slider.SetValue(temperature)
            self.on_temp_scroll(None)
            self.web_search_checkbox.SetValue(value['web_search'])
            self.json_mode_checkbox.SetValue(value['gpt_json'])
            self.batch_mode_checkbox.SetValue(value.get('batch_mode', False))



def _create_client(base_url, environment_var, gui=False):
    """Create an OpenAI client for the given base API configuration."""
    env_var = environment_var
    api_key = os.getenv(env_var, "")

    if api_key is None or api_key == '':
        if gui:
            api_key = ask_api_key(env_var)
        else:
            exit(f'Error: {env_var} environment variable not set.')

    return OpenAI(api_key=api_key, base_url=base_url)


def get_args_compatible(args=None, default_model=None):
    if args is not None:
        allowed_args = ['n', 'temperature', 'max_tokens', 'logprobs', 'stop', 'presence_penalty', 'frequency_penalty']
        gpt_args = dict(arg.split('=') for arg in args.gpt_args if arg in allowed_args) if args.gpt_args else {}
        if 'n' in gpt_args:
            gpt_args['n'] = int(gpt_args['n'])
            if gpt_args['n'] > 100:
                exit('n must be less than 100')
        gpt_model = args.gpt_model
        gpt_json = args.gpt_json
        web_search = args.web_search
        batch_mode = args.batch_mode
    else:
        gpt_args = {}
        gpt_json = True
        web_search = False
        batch_mode = False
        gpt_model = default_model

    return {
        'gpt_args': gpt_args,
        'gpt_model': gpt_model,
        'gpt_json': gpt_json,
        'web_search': web_search,
        'batch_mode': batch_mode,
    }


def _exec_compatible(prompt, gpt_model, gpt_args, gpt_json, batch_mode, web_search, client : OpenAI = None):

    # extract "[data:image/\w+?;base64,{base64 data}]" from the prompt. Convert each occurence to [img1] [img2]
    images = []
    if prompt is not None:
        images = re.findall(r'\[(data:image/\w+?;base64,[A-Za-z0-9+/=]+)\]', prompt)
        for idx, img in enumerate(images):
            prompt = prompt.replace(f'{img}', f'img{idx + 1:02d}')

    api_type = 'chat_completion_api'

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
        web_search = False  # Keep chat_completion_api without web search tool (model already has search capability)

    if web_search:
        api_type = 'response_api'

    if api_type == 'chat_completion_api':
        content = [{"type": "text", "text": prompt},]
        for image in images:
            content.append({
                    "type": "image_url",
                    "image_url": {"url": image}
                })
    else:
        content = [{"type": "input_text", "text": prompt}]
        for image in images:
            content.append({
                    "type": "input_image",
                    "image_url": image,
                })

    #print(json.dumps(content, indent=2, ensure_ascii=False))


    messages = [
        {"role": "user", "content": content}
    ]


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


    if api_type == 'chat_completion_api':
        response = client.chat.completions.create(
            model=gpt_model,
            messages=messages,
            **gpt_args
        )
    elif api_type == 'response_api':

        response_text_options = {}
        tools = []

        if gpt_json:
            response_text_options["format"] = {"type": "json_object"}

        if web_search:
            tools = [{"type": "web_search"}]

        response = client.responses.create(
            model=gpt_model,
            input=messages,
            text=response_text_options,
            temperature=gpt_args['temperature'],
            tools=tools,
        )
    
    response_dump = response.to_dict()
    cost = get_cost(response_dump)

    return {
        'response': response_dump,
        'cost': cost['cost in'] + cost['cost out'],
    }

def ask_api_key(env_var='OPENAI_API_KEY'):
    # This function can be called from any thread
    result = []
    event = threading.Event()

    def show_dialog():
        try:
            dlg = wx.TextEntryDialog(None, f"Please enter your API key ({env_var}):", "API Key", "")
            if dlg.ShowModal() == wx.ID_OK:
                result.append(dlg.GetValue())
            dlg.Destroy()
        except Exception as e:
            print(f"Error showing API key dialog: {e}")
        finally:
            event.set()  # Signal that we're done

    wx.CallAfter(show_dialog)
    event.wait()  # Wait efficiently until the dialog is closed

    return result[0] if result else ""


def exec_delayed_compatible(delayed_content: dict, client: OpenAI):
    jsonl_file_content = []
    batch_ids = set()
    #return

    for key, content in delayed_content.items():
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
        else:
            print(batch.output_file_id, batch.error_file_id)

            # Retrieve the output file content
            if batch.output_file_id is not None:
                file_response = client.files.content(batch.output_file_id)
                jsonl_data = file_response.text
            else:
                jsonl_data = ""

            # Retrieve the error file content
            if batch.error_file_id is not None:
                print(f"Batch {batch_id} has errors.")                
                error_response = client.files.content(batch.error_file_id)
                error_data = error_response.text
            else:
                error_data = ""

            print(len(jsonl_data), len(jsonl_data.splitlines()), len(error_data), len(error_data.splitlines()))
            first_result = True
            for line in jsonl_data.splitlines():
                response_dump = json.loads(line)
                response = response_dump['response']['body']
                custom_id = response_dump['custom_id']
                cost = get_cost(response)
                print("FOUND line in jsonl_data:", custom_id)
                if custom_id.startswith("9a5"):
                    print("DEBUG", cost, response_dump)


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

            for line in error_data.splitlines():
                response_dump = json.loads(line)
                response = response_dump['response']['body']
                custom_id = response_dump['custom_id']
                print("FOUND error on custom_id:", custom_id)
                if response.get('error'):
                    response_error = response['error']['type']  
                else:
                    # Some errors might not have 'error'=null from openai
                    # see https://community.openai.com/t/batch-api-shows-2000-completed-0-failed-but-some-requests-return-status-code-0/1364654
                    response_error = None

                new_delayed_content[custom_id] = {
                    'response': response,
                    'error': response_error,
                    'batch_id': batch_id,
                }

            # Delete the batch input file because we don't need it anymore
            try:
                if batch.input_file_id is not None:
                    client.files.delete(batch.input_file_id)
            except Exception as e:
                print(f"Error deleting batch input file {batch.input_file_id}: {e}")

            try:
                if batch.output_file_id is not None:
                    client.files.delete(batch.output_file_id)
            except Exception as e:
                print(f"Error deleting batch output file {batch.output_file_id}: {e}")

            try:
                if batch.error_file_id is not None:
                    client.files.delete(batch.error_file_id)
            except Exception as e:
                print(f"Error deleting batch error file {batch.error_file_id}: {e}")


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



def show_batch_warning(jsonl_file_content):
    confirmed = False
    if not _gui:
        # Show confirmation input
        print(f"Batch processing is experimental and the cost of the batch cannot be tracked.")
        print(f"Do you want to continue? (y/n): ", end='')
        choice = input().strip().lower()
        confirmed = (choice == 'y')
    else:
        # Ask Continue or Abort
        msg = "Batch processing is experimental and the cost of the batch cannot be tracked.\n\nDo you want to continue?"
        dlg = wx.MessageDialog(None, msg, f"Batch Processing Warning - {len(jsonl_file_content)} item(s)", wx.YES_NO | wx.ICON_WARNING)
        try:
            result = dlg.ShowModal()
        except Exception as e:
            print(f"Error showing batch warning dialog: {e}")
            result = wx.ID_NO
        finally:
            dlg.Destroy()
            
        confirmed = (result == wx.ID_YES)
        
    if not confirmed:
        print("Batch processing aborted by user.")
        raise Exception("Batch processing aborted by user.")
    
   
