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
from importlib.util import spec_from_file_location, module_from_spec
import docx2txt
from pypdf import PdfReader

import itertools
import hashlib

from prompt_blender.rag.embedding import Embedding

from prompt_blender.llms.dummy import MODULE_UUID as DUMMY_MODULE_UUID


FILE_FORMAT_VERSION = "2.0"

SPLIT_ALL_CHUNKS = None

class Model:
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
        if "rag" not in self.data:
            self.data["rag"] = {}

        # Dictionary that stores the colors for each variable
        self.variable_colors = {}

        # Dictionary that stores the selected row for each parameter group
        self.selected_params = defaultdict(int)

        # Complete Path to the file where the model was loaded or saved
        self._file_path = None

        # Flag that indicates if the model has been modified since the last save
        self._is_modified = True

        # Vector database for embeddings
        self._update_embeddings()

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
                
        if version < [2, 0]:
            # {placeholder} -> {{placeholder}} and {{json}} -> {json}
            def migrate_placeholders(text):
                # First replace all {{ and }} with a temporary token
                temp_token_start = "<<§TEMP_START§>>"
                temp_token_end = "<<§TEMP_END§>>"
                text = text.replace("{{", temp_token_start).replace("}}", temp_token_end)
                text = re.sub(r'\{([^{}]+)\}', r'{{\1}}', text)
                text = text.replace(temp_token_start, "{").replace(temp_token_end, "}")
                return text
                
            for prompt_name, prompt_text in data["prompts"].items():
                data["prompts"][prompt_name] = migrate_placeholders(prompt_text)

        data["metadata"]["file_format_version"] = FILE_FORMAT_VERSION
        return data

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
        model.file_path = file_path  # It tracks the file path for future saves
        model.is_modified = False
        return model

    @staticmethod
    def create_from_example(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)

        # Default run configuration
        if 'runs' not in data or not data['runs']:
            data['runs'] = {
                "Dummy Run": {
                    "module_id": DUMMY_MODULE_UUID,
                    "module_args": {
                        "stub_response": "Stub response from the dummy model."
                    }
                }
            }

        model = Model(data)
        model.is_modified = False
        return model

    def validate_runs_modules(self, llm_modules):
        """Valida se todos os runs têm módulos válidos, caso contrário, lança um erro."""
        module_uuids = llm_modules.keys()
        for run_name, run in self.run_configurations.items():
            if run['module_id'] not in module_uuids:
                raise ValueError(f"Module '{run['module_id']}' ({run.get('module_name', '?')}) for run '{run_name}' is not valid.")


    def save_to_file(self, file_path=None):
        if file_path is None:
            file_path = self.file_path
        if file_path is None:
            return False
        
        with open(file_path, 'w', encoding='utf-8') as file:
            self.save_to_fp(file)

        self.file_path = file_path
        self.is_modified = False
        return True

    def save_to_fp(self, fp):
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
        json.dump(self.data, fp, ensure_ascii=False, indent=4)


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

    @property
    def enabled_prompts(self):
        return {k:v for k,v in self.data["prompts"].items() if not self.is_prompt_disabled(k)}

    def get_interpolated_prompt(self, prompt_name):
        _, text = self._interpolate(
            self.data["prompts"][prompt_name], 
            self.get_selected_values()
            )
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

    def set_rag_configuration(self, doc_name, rag_config):
        current_config = self.get_rag_configuration(doc_name)
        if current_config != rag_config:
            self.data["rag"][doc_name] = rag_config
            self.is_modified = True
            self._update_embeddings()

    def remove_rag_configuration(self, doc_name):
        if doc_name in self.data["rag"]:
            self.data["rag"].pop(doc_name)
            self.is_modified = True
            self._update_embeddings()

    def get_rag_configuration(self, doc_name):
        return self.data["rag"].get(doc_name)
    
    def _update_embeddings(self):
        self._embeddings = {k: Embedding(**v) for k,v in self.data["rag"].items()}

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
            if not param:
                continue
            values.update(param[self.selected_params[param_name]])

        return values
    
    def get_functions(self):
        def emb_function(values, k, params, emb):
            if params is None or len(params) == 0:
                raise ValueError("Embedding function requires at least one parameter: the query text variable name.")
            p = params[0]
            if p in values:
                query = values[p]
            else:
                raise ValueError(f"Variable '{p}' not found in values for embedding query.")
            
            ret = emb.query(query_text=query, doc=values[k])

            return ret


        # Embedding Query Functions
        return {k: lambda values, params: emb_function(values, k, params, emb)  for k, emb in self._embeddings.items()}

        #return {
        #    'word': lambda params: '§'.join(params + ['/'])
        #}

    def get_variable_colors(self, variable_name):
        return self.variable_colors.get(variable_name)

    def add_variable_color(self, variable_name):
        if variable_name in self.variable_colors:
            return self.variable_colors[variable_name]
        else:
            color_id = len(self.variable_colors)
            self.variable_colors[variable_name] = color_id
            return color_id

    def refresh_variable_colors(self):
        # Verify every param/key. If key is not present, remove from variable colors
        deleted_variable_colors = set(self.variable_colors.keys())
        for param_name in self.data["parameters"]:
            if not self.data["parameters"][param_name]:
                continue
            for key in self.data["parameters"][param_name][0].keys():
                self.add_variable_color(key)
                deleted_variable_colors.discard(key)

        for variable_name in deleted_variable_colors:
            self.variable_colors.pop(variable_name)

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
        self.refresh_variable_colors()

    def remove_param_key(self, param_name, key):
        param = self.get_parameter(param_name)
        if param:
            for row in param:
                row.pop(key, None)

            # Remove all registers that have no keys
            self.data["parameters"][param_name] = [row for row in param if row]

            self.is_modified = True
        self.refresh_variable_colors()

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

    def add_table_from_directory(self, directory_path, encoding='utf-8', split_length=8000000, split_count=SPLIT_ALL_CHUNKS, variable='dir'):
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
        self.add_param(variable, param)

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

    def add_table_from_string(self, content, extension, maximum_rows=1000):
        # Create system temporary file
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix=f'.{extension}', encoding='utf-8') as file:
            file.write(content)
            file.close()
            file_path = file.name
            self.add_table_from_file(file_path, variable='value', maximum_rows=maximum_rows)

    def add_table_from_file(self, file_path, encoding='utf-8', variable=None, separator=',', maximum_rows=1000):
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

        if len(param) > maximum_rows:
            raise ValueError(
                f"The file contains more than {maximum_rows} rows. Please, reduce the number of rows to load.")
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
        values = self.get_selected_values()

        tag_positions, _ = self._interpolate(
            self.data["prompts"][prompt_name], values, replace=interpolated)
        return tag_positions


    @staticmethod
    def _to_str(value):
        """Convert a value to string for interpolation.
        
        None and NaN are converted to empty string.
        Other non-string types are converted via str().
        """
        if value is None:
            return ""
        if isinstance(value, float) and value != value:  # NaN check
            return ""
        if not isinstance(value, str):
            return str(value)
        return value

    def _extract_placeholders(self, text, values=None, functions=None, raise_on_missing=False) -> list:
        placeholders = []

        for match in re.finditer(r'\{\{([^{}]*)\}\}', text):
            placeholder = match.group(1)
            if placeholder in placeholders:
                continue

            # If placeholder is in format <var>(.*)... let var_name be the left part and params be the right part
            m = re.match(r'([^()]+)\((.*)\)', placeholder)
            if m:
                var_name, f_params = m.groups()
                f_params = [f.strip() for f in f_params.split(',')]
            else:
                var_name = placeholder
                f_params = None

            start = match.start()
            end = match.end()

            replacement_value = None

            if f_params is None and values is not None and var_name in values:
                replacement_value = self._to_str(values.get(var_name))
            elif functions is not None and var_name in functions:
                replacement_value = str(functions[var_name](values, f_params))
            else:
                if raise_on_missing:
                    raise ValueError(f'Error: Prompt contains argument "{var_name}", but it was not found in the input arguments.')
                else:
                    replacement_value = f"[!! Missing Variable: {var_name} !!]"

            placeholders.append({
                'placeholder': placeholder,
                'var_name': var_name,
                'function_params': f_params,
                'start': start,
                'end': end,
                'value': replacement_value
            })

        return placeholders


    def _interpolate(self, text, values, replace=True, raise_on_missing=False):
        tag_positions = []
        new_text = text
        offset = 0

        functions = self.get_functions()

        for placeholder in self._extract_placeholders(text, values, functions, raise_on_missing=raise_on_missing):

            var_name = placeholder['var_name']
            start = placeholder['start'] + offset
            end = placeholder['end'] + offset

            if replace:
                replacement_value = placeholder['value']

                new_text = new_text[:start] + replacement_value + new_text[end:]
                offset += len(replacement_value) - (end - start)
                end = start + len(replacement_value)

            # Salvando as posições para aplicar a coloração
            tag_positions.append((var_name, start, end))

        return tag_positions, new_text

    def get_run_args(self, llm_modules: dict = None):
        run_args = {}

        for name, run_configuration in self.run_configurations.items():
            module_id = run_configuration['module_id']
            if llm_modules is None or module_id not in llm_modules:
                run_args[name] = None
            else:
                llm_module = llm_modules[module_id]

                module_info = llm_module.module_info
                module_name = module_info['name']
                args = run_configuration['module_args']
                hash_args = hashlib.md5(json.dumps(args, sort_keys=True).encode()).hexdigest()
                run_hash = f'{module_info["cache_prefix"]}_{hash_args}'

                run_args[name] = {
                    'llm_module': llm_module,
                    'module_info': module_info,
                    'module_name': module_name,
                    'args': args,
                    'run_hash': run_hash
                }
            
        return run_args
   

    def get_parameter_combinations(self, callback=None):
        prompts = [{'_id': prompt_name, 'prompt': prompt} for prompt_name, prompt in self.enabled_prompts.items()]

        # Create parameters combinations, such that each combination has a unique tuple (i0, i1, i2, ...)
        parameters = [prompts] + list(self.parameters.values())

        num_combinations = self.get_num_combinations()
        if callback:
            keep_running = callback(0, num_combinations)
        else:
            keep_running = True


        for i, combination in enumerate(itertools.product(*parameters)):
            prompt_arguments = self._flat_values(combination)
            #placeholders = self._extract_placeholders(combination[0]['prompt'], prompt_arguments, self.get_functions())
            _, new_prompt = self._interpolate(combination[0]['prompt'], prompt_arguments, replace=True, raise_on_missing=True)
            yield ParameterCombination(combination, prompt=new_prompt)

            if callback:
                keep_running = callback(i+1, num_combinations)
                if keep_running is False:
                    break

    def get_current_combination(self, prompt_name):
        prompt = self.data["prompts"][prompt_name]
        parameters = [{'_id': prompt_name, 'prompt': prompt}] + [self.get_selected_values()]

        prompt_arguments = self._flat_values(parameters)
        #placeholders = self._extract_placeholders(prompt, prompt_arguments, self.get_functions())
        _, new_prompt = self._interpolate(prompt, prompt_arguments, replace=True, raise_on_missing=True)
        return ParameterCombination(parameters, prompt=new_prompt)

    def _flat_values(self, parameters):
        prompt_arguments = {}
        for argument in parameters:
            values = {k:v for k,v in argument.items() if not k.startswith('_')}
            prompt_arguments.update(values)
        return prompt_arguments

  


    def get_num_combinations(self):
        # Calculate multiplication of all parameter lengths
        num_combinations = len(self.enabled_prompts)
        for parameter in self.parameters.values():
            num_combinations *= len(parameter)
        #print('Number of combinations:', num_combinations)
        return num_combinations
    

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
    
class ParameterCombination:
    def __init__(self, combination: list, prompt: str) -> None:
        prompt_arguments = {}  # Arguments used in the prompt expansion
        prompt_arguments_masked = {}  # Arguments used in the prompt expansion, but masked when an _id is present

        for argument in combination:
            values = {k:v for k,v in argument.items() if not k.startswith('_')}
            id = argument.get('_id', None)
            if not id:
                prompt_arguments_masked.update(values)
            else:
                prompt_arguments_masked.update({k: (id if isinstance(v, str) else v)
                                                for k,v in values.items()})

            prompt_arguments.update(values)

        self._prompt_content = prompt
        self._missing_argument = None

        # Calculate non-cryptographic hash of the prompt content
        # sha1 cryptographic hash of the prompt content
        self._prompt_hash = hashlib.sha1(self._prompt_content.encode()).hexdigest()
        filepath = os.path.join('cache', self._prompt_hash[:2], self._prompt_hash)

        self._prompt_arguments = prompt_arguments
        self._prompt_arguments_masked = prompt_arguments_masked
        self._filepath = filepath
        self._prompt_file = os.path.join(filepath, 'prompt.txt')

    @property
    def prompt_file(self):
        return self._prompt_file
    
    @property
    def prompt_content(self):
        return self._prompt_content
    
    @property
    def missing_argument(self):
        return self._missing_argument
    
    def get_result_file(self, run_hash: str):
        return os.path.join(self._filepath, f'result_{run_hash}.json')

    @property
    def filepath(self):
        return self._filepath
    
    @property
    def prompt_hash(self):
        return self._prompt_hash
        
