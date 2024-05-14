import re
from collections import defaultdict
import os
from pathlib import Path
import pyperclip
import json
from datetime import datetime
from prompt_blender import info
from prompt_blender.arguments import Config, ParameterCombination
from importlib.util import spec_from_file_location, module_from_spec

class Model:
    # Cores com contraste suficiente para serem usadas no highlight, sobre um fundo branco
    default_colors = [
        '#FF0000',  # Vermelho
        '#00FF00',  # Verde
        '#0000FF',  # Azul
        '#A0A000',  # Amarelo
        '#FF00FF',  # Magenta
        '#00FFFF',  # Ciano
        '#FFA500',  # Laranja
        '#800080',  # Roxo
        '#008000',  # Verde escuro
        '#000080',  # Azul escuro
        '#800000',  # Marrom
        '#808000',  # Oliva
        '#008080',  # Verde azulado
    ]

    def __init__(self, data) -> None:
        # Dictionary that represents the project data
        self.data = data

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

    @staticmethod
    def create_from_template():
        data = {
            "parameters": [
              [
                {"_id": "orgao1.txt", "document_text": "Texto representando os termos de confidencialidade do órgão 1."},
                {"_id": "orgao2.txt", "document_text": "Texto representando os termos de confidencialidade do órgão 2."},
                {"_id": "orgao3.txt", "document_text": "Texto representando os termos de confidencialidade do órgão 3."}
              ],
              [
                {"criterion": "Finalidade do tratamento dos dados"},
                {"criterion": "Teste de critério"},
                {"criterion": "Formação de perfil"},
                {"criterion": "Exclusão de dados"},
                {"criterion": "Segurança dos dados"},
                {"criterion": "Compartilhamento de dados"},
                {"criterion": "Direitos do titular dos dados"},
                {"criterion": "Responsabilidade"},
                {"criterion": "Transferência internacional de conhecimento"},
                # Mais critérios podem ser adicionados aqui
              ]
            ],
            "prompts": [
                "Teste de {criterion}.",
                "Avalie o termo de confidencialidade representado em aspas triplas quanto ao critério '{criterion}'. Descreva como este termo aborda o critério mencionado e forneça uma pontuação de 1 a 10 para a eficácia com que este critério é tratado. Responda no seguinte formato de saída JSON: {{'text': 'Descrição e pontuação para o critério.'}}.\n\n \"\"\"{document_text}\"\"\"",
                "Avalie o termo de confidencialidade representado em aspas triplas quanto ao critério '{criterion}'. Descreva como este termo aborda o critério mencionado e forneça uma pontuação de 1 a 10 para a eficácia com que este critério é tratado. Responda no seguinte formato de saída JSON: {{'text': '<Justifique a seleção para o critério.>',\n'pontuação': <Pontuação de 1 a 5, conforme a aderência>}}.\n\n \"\"\"{document_text}\"\"\""
            ]
        }     
        return Model(data)

    @staticmethod
    def create_from_clipboard():   
        s = pyperclip.paste()
        data = json.loads(s)
        return Model(data)

    @staticmethod
    def create_empty():
        data = {
            "parameters": [],
            "prompts": []
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
        metadata.update({"modified_time": datetime.now().astimezone().isoformat()})
        metadata.update({'app_version': info.__version__})
        self.data["metadata"] = metadata
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(self.data, file, ensure_ascii=False, indent=4)
        self.file_path = file_path
        self.is_modified = False
        return True

    def to_dict(self):
        return self.data

    def get_prompt(self, prompt_id):
        return self.data["prompts"][prompt_id]
    
    def set_prompt(self, prompt_id, prompt_text):
        self.data["prompts"][prompt_id] = prompt_text
        self.is_modified = True

    def get_interpolated_prompt(self, prompt_id):
        _, text = self._interpolate(self.data["prompts"][prompt_id], self.get_selected_values())
        return text

    def get_number_of_prompts(self):
        return len(self.data["prompts"])
    
    def add_prompt(self, prompt_text=""):
        self.data["prompts"].append(prompt_text)
        self.is_modified = True

    def remove_prompt(self, prompt_id):
        self.data["prompts"].pop(prompt_id)
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
        #Obtenha o values de todos os parâmetros selecionados
        values = {}
        for i, param in enumerate(self.parameters):
            values.update(param[self.selected_params[i]])

        return values

    def get_variable_colors(self, variable_name):

        if self.variable_colors.get(variable_name) is None:
            # Seleciona as cores em ordem de aparição no default_colors
            self.variable_colors[variable_name] = self.default_colors[len(self.variable_colors) % len(self.default_colors)]

        return self.variable_colors.get(variable_name)

    def get_parameter(self, param_id):
        if param_id < 0 or param_id >= len(self.data["parameters"]):
            return None
        return self.data["parameters"][param_id]

    def set_selected_item(self, param_id, selected_row):
        self.selected_params[param_id] = selected_row

    def get_selected_item(self, param_id):
        return self.selected_params[param_id]
    
    def add_param(self, param):
        if param:
            self.data["parameters"].append(param)
            self.is_modified = True

    def remove_param(self, param_id):
        self.data["parameters"].pop(param_id)
        self.is_modified = True

    def move_param(self, param_id, direction: int):
        new_param_id = param_id + direction
        # direction can be -1 or 1
        if 0 <= new_param_id < len(self.data["parameters"]):
            # Swap the parameters positions
            self.data["parameters"][param_id], self.data["parameters"][param_id + direction] = self.data["parameters"][param_id + direction], self.data["parameters"][param_id]
            self.is_modified = True
            return new_param_id
        else:
            return param_id

    def add_param_directory(self, directory_path):
        param = []
        for file in os.listdir(directory_path):
            if file.endswith(".txt"):
                f = os.path.join(directory_path, file)
                param.append({'_id': file, 'document_text': Path(f).read_text()})
        self.add_param(param)     

    def add_param_file(self, file_path, encoding='utf-8'):
        variable, extension = os.path.basename(file_path).split('.')
        extension = extension.lower()

        import pandas as pd
        if extension in ('xlsx', 'xls'):
            df = pd.read_excel(file_path, encoding=encoding)
            param = df.to_dict(orient='records')
        elif extension in ('csv',):
            df = pd.read_csv(file_path, encoding=encoding)
            param = df.to_dict(orient='records')
        elif extension in ('txt',):
            with open(file_path, 'r', encoding=encoding) as file:
                lines = file.readlines()
                param = [{variable: line} for line in lines]
        elif extension in ('jsonl',):
            with open(file_path, 'r', encoding=encoding) as file:
                lines = file.readlines()
                param = [json.loads(line) for line in lines]
        elif extension in ('json',):
            with open(file_path, 'r', encoding=encoding) as file:
                param = json.load(file)
            # Check if the json is a list of dictionaries
            if not isinstance(param, list) or not all(isinstance(x, dict) for x in param):
                raise ValueError("JSON file must contain a list of dictionaries")
        elif extension in ('py',):
            spec = spec_from_file_location("", file_path)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'generate'):
                param = module.generate()
            else:
                raise ValueError("The module must contain a 'generate'function")
        
        print(len(param))
        if len(param) > 1000:
            raise ValueError("The file contains more than 1000 rows. Please, reduce the number of rows to load.")
        self.add_param(param)     

    def apply_transform(self, param_id, transform_file):
        param = self.get_parameter(param_id)
        if param:
            spec = spec_from_file_location("", transform_file)
            module = module_from_spec(spec)
            spec.loader.exec_module(module)
            if hasattr(module, 'apply_transform'):
                for i, row in enumerate(param):
                    param[i].update(module.apply_transform(row))
            else:
                raise ValueError("The module must contain a 'apply_transform' function")

    def truncate_param(self, param_id, max_rows):
        param = self.get_parameter(param_id)
        if param:
            self.data["parameters"][param_id] = param[:max_rows]
            self.is_modified = True

    def get_hightlight_positions(self, prompt_id, interpolated):
        if interpolated:
            values = self.get_selected_values()
        else:
            values = None

        tag_positions, _ = self._interpolate(self.data["prompts"][prompt_id], values)
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
                value = values.get(var_name, f"[!! Missing Variable: {var_name} !!]")
                new_text = new_text[:start] + value + new_text[end:]
                offset += len(value) - (end - start)
                end = start + len(value)
                print(f"Substituindo {var_name} por {value} na posição {start} até {end} (offset {offset})")

            # Salvando as posições para aplicar a coloração
            tag_positions.append((var_name, start, end))

        return tag_positions, new_text
    
    def get_result(self, prompt_id, output_dir, result_name):
        config = Config.load_from_dict(self.data)
        combination = config.get_parameter_combination(prompt_id, self.get_selected_values())
        result_file = os.path.join(output_dir, combination.get_result_file(result_name))
        if os.path.exists(result_file):
            with open(result_file, 'r') as file:
                return file.read()
        else:
            return None
