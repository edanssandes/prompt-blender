import re
import os
import pyperclip
import json
import base64
import tempfile
import pandas as pd
from collections import defaultdict
from pathlib import Path
from datetime import datetime
from prompt_blender import info
from prompt_blender.arguments import Config, ParameterCombination
from importlib.util import spec_from_file_location, module_from_spec
import docx2txt
from PyPDF2 import PdfReader

FILE_FORMAT_VERSION = "1.0"

SPLIT_ALL_CHUNKS = None

class Model:
    # Cores com contraste suficiente para serem usadas no highlight, sobre um fundo branco
    default_colors = [
        '#00AA00',  # Verde
        '#0030FF',  # Azul
        '#A0A000',  # Amarelo
        '#FF00FF',  # Magenta
        '#00FFFF',  # Ciano
        '#FFA500',  # Laranja
        '#800080',  # Roxo
        '#008000',  # Verde escuro
        '#404040',  # Cinza escuro
        '#000080',  # Azul escuro
        '#800000',  # Marrom
        '#808000',  # Oliva
        '#008080',  # Verde azulado
        '#808080',  # Cinza
    ]

    def __init__(self, data) -> None:
        # Dictionary that represents the project data
        self.data = Model.migrate(data)

        # Loading default values for the data structure, if not present
        if "runs" not in self.data:
            self.data["runs"] = {}
        if "prompts" not in self.data:
            self.data["prompts"] = {}
        if "parameters" not in self.data:
            self.data["parameters"] = {}

        # Dictionary that stores the colors for each variable
        self.variable_colors = {}

        # Dictionary that stores the selected row for each parameter group
        self.selected_params = defaultdict(int)

        # Complete Path to the file where the model was loaded or saved
        self._file_path = None

        # Flag that indicates if the model has been modified since the last save
        self._is_modified = True

        # Set of functions to be called when the model changes state
        self.on_modified_callbacks = set()

    def migrate(data):
        if "metadata" not in data:
            return data
        version_str = data.get("metadata", {}).get("file_format_version", "0.0")
        version = [int(v) for v in version_str.split('.')]

        if version > [int(x) for x in FILE_FORMAT_VERSION.split('.')]:
            raise ValueError(
                f"File format version {version_str} is not supported. Please, use a compatible version of Prompt Blender.")
        
        if version < [1, 0]:
            if isinstance(data["parameters"], list):
                data["parameters"] = {
                    f"Parameter {i}": param for i, param in enumerate(data["parameters"])}
            if isinstance(data["prompts"], list):
                data["prompts"] = {f"Prompt {i}": prompt for i,
                                   prompt in enumerate(data["prompts"])}

        data["metadata"]["file_format_version"] = FILE_FORMAT_VERSION
        return data

    @staticmethod
    def create_from_template():
        data = {
            "parameters": {
                "Celsius": [
                    {"celsius_value": 4},
                    {"celsius_value": 22},
                    {"celsius_value": 100}
                ],
                "Fahrenheit": [
                    {"fahrenheit_values": 39.2},
                    {"fahrenheit_values": 71.6},
                    {"fahrenheit_values": 212}
                ]
            },
            "prompts": {
                "Celsius to Fahrenheit": "A temperature of {celsius_value}°C is measured in Celsius.\nThe corresponding Fahrenheit reading was {fahrenheit_values}°F.\nUsing the formula F = (9/5) * C + 32, calculate the expected Fahrenheit value for {celsius_value}°C.\nCompare the calculated Fahrenheit value with the measured value.\n\nProvide the result in the following output JSON format:\n{{\n\t\"calculated_fahrenheit\": <calculated value>,\n\t\"measured_fahrenheit\": <measured value>,\n\t\"difference\": <absolute difference>,\n\t\"match\": <true if they match, else false>\n}}.",
                "Fahrenheit to Celsius": "A temperature of {fahrenheit_values}°F is measured in Fahrenheit.\nThe corresponding Celsius reading was {celsius_value}°C.\nUsing the formula C = (5/9) * (F - 32), calculate the expected Celsius value for {fahrenheit_values}°F.\nCompare the calculated Celsius value with the original Celsius reading.\n\nProvide the result in the following output JSON format:\n{{\n\t\"calculated_celsius\": <calculated value>,\n\t\"measured_celsius\": <measured value>,\n\t\"difference\": <absolute difference>,\n\t\"match\": <true if they match, else false>\n}}."
            },
            "runs": {
                "Teste 1": {
                    "module_id": "66981b2d-3b8b-473a-9caf-3cd9c329f5d7",
                    "module_args": {
                        "stub_response": "Stub response from the dummy model. #1"
                    }
                }
            }
        }

        model = Model(data)
        model.is_modified = False
        return model

    @staticmethod
    def create_from_clipboard():
        s = pyperclip.paste()
        data = json.loads(s)
        return Model(data)

    @staticmethod
    def create_empty():
        data = {
            "parameters": {},
            "prompts": {},
            "runs": {},
        }
        return Model(data)

    @staticmethod
    def create_from_file(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
        model = Model(data)
        model.file_path = file_path
        model.is_modified = False
        return model

    def save_to_file(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        if file_path is None:
            return False
        metadata = self.data.get("metadata", {})
        # save local time with timezone in isoformat
        metadata.update(
            {"modified_time": datetime.now().astimezone().isoformat()})
        metadata.update({
                'app_name': info.APP_NAME,
                'app_version': info.__version__,
                'file_format_version': FILE_FORMAT_VERSION
            })
        self.data["metadata"] = metadata
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(self.data, file, ensure_ascii=False, indent=4)
        self.file_path = file_path
        self.is_modified = False
        return True

    def to_dict(self):
        return self.data

    def get_prompt(self, prompt_name):
        return self.data["prompts"][prompt_name]

    def set_prompt(self, prompt_name, prompt_text):
        if self.data["prompts"].get(prompt_name) != prompt_text:
            self.data["prompts"][prompt_name] = prompt_text
            self.is_modified = True

    def is_prompt_disabled(self, prompt_name):
        disabled_prompts = self.data.get("disabled_prompts", [])
        return prompt_name in disabled_prompts

    def set_prompt_disabled(self, prompt_name, disabled):
        disabled_prompts = self.data.get("disabled_prompts", [])
        if disabled:
            if prompt_name not in disabled_prompts:
                disabled_prompts.append(prompt_name)
                self.is_modified = True
        else:
            if prompt_name in disabled_prompts:
                disabled_prompts.remove(prompt_name)
                self.is_modified = True
        self.data["disabled_prompts"] = disabled_prompts

    def get_interpolated_prompt(self, prompt_name):
        _, text = self._interpolate(
            self.data["prompts"][prompt_name], self.get_selected_values())
        return text

    def get_prompt_names(self):
        return self.data["prompts"].keys()

    def get_number_of_prompts(self):
        return len(self.data["prompts"])

    def get_new_prompt_name(self, prompt_prefix=None):
        if prompt_prefix is None:
            prompt_prefix = "New Prompt"
        prompt_complement = 0
        prompt_name = prompt_prefix
        while prompt_name in self.data["prompts"]:
            prompt_complement += 1
            prompt_name = f"{prompt_prefix} {prompt_complement}"
        return prompt_name

    def get_new_param_name(self, param_prefix=None):
        if param_prefix is None:
            param_prefix = "New Parameter"
        param_complement = 0
        param_name = param_prefix
        while param_name in self.data["parameters"]:
            param_complement += 1
            param_name = f"{param_prefix} {param_complement}"
        return param_name

    def add_prompt(self, prompt_name=None, prompt_text=""):
        new_prompt_name = self.get_new_prompt_name(prompt_name)
        self.data["prompts"][new_prompt_name] = prompt_text
        self.is_modified = True

        return new_prompt_name

    def remove_prompt(self, prompt_name):
        self.data["prompts"].pop(prompt_name)
        self.is_modified = True

    def rename_prompt(self, prompt_name, new_name):
        # Check if the new name already exists
        if new_name in self.data["prompts"]:
            return False

        # Use itens to keep dictionary order
        prompts = list(self.data["prompts"].items())
        prompt_index = list(self.data["prompts"].keys()).index(prompt_name)
        prompts[prompt_index] = (new_name, prompts[prompt_index][1])
        self.data["prompts"] = dict(prompts)

        self.is_modified = True

        # Rename disabled prompt if it exists
        disabled_prompts = self.data.get("disabled_prompts", [])
        if prompt_name in disabled_prompts:
            disabled_prompts.remove(prompt_name)
            disabled_prompts.append(new_name)
            self.data["disabled_prompts"] = disabled_prompts

        return True

    @property
    def run_configurations(self):
        return self.data["runs"]
    
    @run_configurations.setter
    def run_configurations(self, value):
        if value != self.data["runs"]:
            self.data["runs"] = value
            self.is_modified = True

    @property
    def file_path(self):
        return self._file_path

    @property
    def is_modified(self):
        return self._is_modified

    @file_path.setter
    def file_path(self, value):
        if value != self._file_path:
            self._file_path = value
            self.notify_modified()

    @is_modified.setter
    def is_modified(self, value):
        if value != self._is_modified:
            self._is_modified = value
            self.notify_modified()

    def notify_modified(self):
        for callback in self.on_modified_callbacks:
            callback()

    def add_on_modified_callback(self, callback):
        self.on_modified_callbacks.add(callback)

    @property
    def parameters(self):
        return self.data["parameters"]

    def get_selected_values(self):
        # Obtenha o values de todos os parâmetros selecionados
        values = {}
        for param_name, param in self.parameters.items():
            values.update(param[self.selected_params[param_name]])

        return values

    def get_variable_colors(self, variable_name):
        return self.variable_colors.get(variable_name)

    def add_variable_color(self, variable_name):
        if variable_name in self.variable_colors:
            return self.variable_colors[variable_name]
        else:
            color = self.default_colors[len(
                self.variable_colors) % len(self.default_colors)]
            self.variable_colors[variable_name] = color
            return color

    def get_parameter(self, param_name):
        if param_name not in self.data["parameters"]:
            return None
        return self.data["parameters"][param_name]

    def get_first_parameter(self):
        if self.data["parameters"]:
            # First element from dict_keys from data["parameters"]
            return self.data["parameters"].keys().__iter__().__next__()
        else:
            return None

    def set_selected_item(self, param_name, selected_row):
        self.selected_params[param_name] = selected_row

    def get_selected_item(self, param_name):
        return self.selected_params[param_name]

    def add_param(self, param_name, param):
        if param:
            new_param_name = self.get_new_param_name(param_name)
            self.data["parameters"][new_param_name] = param
            self.is_modified = True

    def remove_param(self, param_name):
        self.data["parameters"].pop(param_name)
        self.is_modified = True

    def remove_param_key(self, param_name, key):
        param = self.get_parameter(param_name)
        if param:
            for row in param:
                row.pop(key, None)

            # Remove all registers that have no keys
            self.data["parameters"][param_name] = [row for row in param if row]

            self.is_modified = True

    def move_param(self, param_name, direction: int):
        param_index = list(self.data["parameters"].keys()).index(param_name)
        swap_index = param_index + direction
        p0, p1 = min(param_index, swap_index), max(param_index, swap_index)
        if 0 <= swap_index < len(self.data["parameters"]):
            items = list(self.data["parameters"].items())
            self.data["parameters"] = dict(
                items[:p0] +
                [items[p1]] +
                [items[p0]] +
                items[p1+1:]
            )
            self.is_modified = True

    def add_table_from_directory(self, directory_path, encoding='utf-8', split_length=8000000, split_count=SPLIT_ALL_CHUNKS):
        param = []
        errors = []
        for file in os.listdir(directory_path):
            print("Reading file:", file)
            file_lower = file.lower()
            f = os.path.join(directory_path, file)
            try:
                p = self._get_params_from_file(encoding, split_length, file, file_lower, f, split_count)
                param += p
            except Exception as e:
                print(f"Error reading file {file}: {e}")
                errors.append(file)
                continue

        if errors:
            raise ValueError(
                f"Errors reading files: {errors}. Please, check the files and try again.")
        self.add_param('dir', param)

    def _get_params_from_file(self, encoding, split_length, file, file_lower, f, split_count):
        param = []
        text = None
        image = None
        if file_lower.endswith(".txt"):
            text = Path(f).read_text(encoding=encoding)
        elif file_lower.endswith(".pdf"):
            text = self.convert_pdf_to_txt(f)
        elif file_lower.endswith(".docx"):
            text = self.convert_docx_to_txt(f)
        elif file_lower.endswith((".jpeg", ".jpg", ".png", ".gif", ".webp")):
            # read content as f"data:image/jpeg;base64,{base64_image}"
            content = Path(f).read_bytes()
            content_length = len(content)
            base64_image = base64.b64encode(content).decode('utf-8')
            prefix = file_lower.split('.')[-1]
            mime_type = {
                'jpeg': 'image/jpeg',
                'jpg': 'image/jpeg',
                'png': 'image/png',
                'gif': 'image/gif',
                'webp': 'image/webp',
            }
            
            image = f"[data:{mime_type[prefix]};base64,{base64_image}]"
            

        if text is not None:
            if len(text) > split_length:
                    # Split text into chunks
                chunks = [text[i:i+split_length]
                              for i in range(0, len(text), split_length)]
                for i, chunk in enumerate(chunks):
                    param.append(
                            {'_id': f"{file}_part_{i:03}", 'document_text': chunk, 'document_size': len(chunk)})
            else:
                param.append(
                        {'_id': file, 'document_text': text, 'document_size': len(text)})
                
        if image is not None:
            param.append(
                {'_id': file, 'image': image, 'image_size': content_length})

        if not split_count:
            return param
        elif split_count < 0:
            return param[-split_count:]
        else:
            return param[:split_count]

    def convert_docx_to_txt(self, input_path):
        text = docx2txt.process(input_path)
        return text

    def convert_pdf_to_txt(self, input_path):
        reader = PdfReader(input_path)
        text = ''
        for page in reader.pages:
            text += page.extract_text()
        return text

    def add_table_from_string(self, content, extension):
        # Create system temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'.{extension}', encoding='utf-8') as file:
            file.write(content)
            file.close()
            file_path = file.name
            self.add_table_from_file(file_path, variable='value')

    def add_table_from_file(self, file_path, encoding='utf-8', variable=None, separator=','):
        _variable, extension = os.path.basename(file_path).split('.')
        extension = extension.lower()
        if variable is None:
            variable = _variable

        if extension in ('xlsx', 'xls'):
            df = pd.read_excel(file_path)
            param = df.to_dict(orient='records')
        elif extension in ('csv',):
            # read csv - all strings
            df = pd.read_csv(file_path, encoding=encoding, sep=separator, dtype=str)
            param = df.to_dict(orient='records')
        elif extension in ('txt',):
            with open(file_path, 'r', encoding=encoding) as file:
                lines = file.readlines()
                param = [{variable: line.strip()} for line in lines]
        elif extension in ('jsonl',):
            with open(file_path, 'r', encoding=encoding) as file:
                lines = file.readlines()
                param = [json.loads(line) for line in lines]
        elif extension in ('json',):
            with open(file_path, 'r', encoding=encoding) as file:
                param = json.load(file)
            # Check if the json is a list of dictionaries
            if not isinstance(param, list) or not all(isinstance(x, dict) for x in param):
                raise ValueError(
                    "JSON file must contain a list of dictionaries")
        elif extension in ('py',):
            spec = spec_from_file_location("", file_path)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'generate'):
                param = module.generate()
            else:
                raise ValueError(
                    "The module must contain a 'generate'function")

        if len(param) > 1000:
            raise ValueError(
                "The file contains more than 1000 rows. Please, reduce the number of rows to load.")
        self.add_param(variable, param)

    def apply_transform(self, param_name, transform_file):
        param = self.get_parameter(param_name)
        if param:
            spec = spec_from_file_location("", transform_file)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'apply_transform'):
                for i, row in enumerate(param):
                    print("*****")
                    print(i, row['document_text'])
                    param[i].update(module.apply_transform(row))
            else:
                raise ValueError(
                    "The module must contain a 'apply_transform' function")

    def truncate_param(self, param_name, max_rows):
        param = self.get_parameter(param_name)
        if param:
            self.data["parameters"][param_name] = param[:max_rows]
            self.is_modified = True
            self.selected_params[param_name] = min(self.selected_params[param_name], max_rows - 1)

    def remove_duplicates(self, param_name):
        param = self.get_parameter(param_name)
        if param:
            # PAram is a list of dictionaries
            without_duplicates = [dict(t)
                                  for t in {tuple(d.items()) for d in param}]
            if len(without_duplicates) < len(param):
                self.data["parameters"][param_name] = without_duplicates
                self.is_modified = True

    def rename_variable(self, param_name, old_key, new_key):
        param = self.get_parameter(param_name)
        if param:
            for row in param:
                row[new_key] = row.pop(old_key)
                # change color
                if old_key in self.variable_colors:
                    self.variable_colors[new_key] = self.variable_colors.pop(
                        old_key)
            self.is_modified = True

    def rename_table(self, param_name, new_name):
        # Rename self.data["parameters"][new_name] but keep the same key order
        key_index = list(self.data["parameters"].keys()).index(param_name)
        self.data["parameters"] = dict(
            list(self.data["parameters"].items())[:key_index] +
            [(new_name, self.data["parameters"][param_name])] +
            list(self.data["parameters"].items())[key_index+1:])
        self.is_modified = True

    def get_hightlight_positions(self, prompt_name, interpolated):
        if interpolated:
            values = self.get_selected_values()
        else:
            values = None

        tag_positions, _ = self._interpolate(
            self.data["prompts"][prompt_name], values)
        return tag_positions

    def _interpolate(self, text, values):
        tag_positions = []
        new_text = text
        offset = 0

        for match in re.finditer(r'(?<!\{)\{([^{}]*)\}(?!\})', text):
            var_name = match.group(1)
            start = match.start() + offset
            end = match.end() + offset
            if values:
                value = str(values.get(
                    var_name, f"[!! Missing Variable: {var_name} !!]"))
                new_text = new_text[:start] + value + new_text[end:]
                offset += len(value) - (end - start)
                end = start + len(value)
                print(
                    f"Substituindo {var_name} por {value} na posição {start} até {end} (offset {offset})")

            # Salvando as posições para aplicar a coloração
            tag_positions.append((var_name, start, end))

        return tag_positions, new_text


    def get_current_combination(self, prompt_name):
        config = Config.load_from_dict(self.data)
        combination = config.get_parameter_combination(prompt_name, self.get_selected_values())
        return combination

    def get_result_files(self, prompt_name, output_dir, run_hashes):
        combination = self.get_current_combination(prompt_name)
        
        return {run_name: os.path.join(output_dir, combination.get_result_file(run_hash)) 
                for run_name, run_hash in run_hashes.items()}


    def get_result(self, prompt_name, output_dir, run_hashes):

        result_files = self.get_result_files(prompt_name, output_dir, run_hashes)
        
        results = {}

        for run_name, result_file in result_files.items():        
            result_content_json = None
            if os.path.exists(result_file):
                with open(result_file, 'r', encoding='utf-8') as file:
                    result_content_json = file.read()

            # Convert JSON to a formatted string
            result_content = None
            if result_content_json:
                try:
                    result_data = json.loads(result_content_json)
                    result_content = json.dumps(result_data, indent=4, ensure_ascii=False)

                    # Decode json strings with \\n, \\t, \\"
                    result_content = result_content.replace('\\n', '\n')
                    result_content = result_content.replace('\\t', '\t')
                    result_content = result_content.replace('\\"', '"')

                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON from {result_file}: {e}")
                    result_content = f"Error decoding JSON: {e}"
            
            results[run_name] = result_content
        
        # if all results are null
        if not any(results.values()):
            return None

        sep = "=" * 80
        full_results = ""
        for run_name, result_content in results.items():
            full_results += f"{sep}\nRun: {run_name}\n{sep}\n"
            if result_content:
                full_results += result_content
            else:
                full_results += "No result found"
            full_results += "\n"*4

        #print(f"Full results for prompt '{prompt_name}':\n{full_results}")
        return full_results