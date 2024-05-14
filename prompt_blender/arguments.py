import pandas as pd
import importlib.util
import os
from pathlib import Path
import itertools
import json
import hashlib

class Config:
    def __init__(self, parameters=None, prompts=None):
        self._parameters = parameters
        self._prompts = prompts

    @staticmethod
    def load_from_dir(directory: str):

        input_dir = os.path.join(directory, 'input')
        if os.path.isdir(input_dir):
            parameter_files = [os.path.join(input_dir, name) for name in sorted(os.listdir(input_dir)) if not name.startswith('_')]
        else:
            parameter_files = []


        prompt_file = os.path.join(directory, 'prompt.txt')
        # Read all prompt files in the directory. Pattern: prompt*.txt
        prompt_files = [os.path.join(directory, name) for name in sorted(os.listdir(directory)) if name.startswith('prompt') and name.endswith('.txt')]

        prompt_contents = []
        for prompt_file in prompt_files:
            with open(prompt_file, 'r') as file:
                prompt_content = file.read()
                prompt_contents.append(prompt_content)

        parameters = [
            _get_argument_values(arg)
            for arg in parameter_files
        ]

        for k, v in zip(parameter_files, parameters):
            print(f'{k:>10s}: {len(v)} values')


        config = Config(parameters=parameters, prompts=prompt_contents)

        return config


    @staticmethod
    def load_from_json(json_file: str):
        with open(json_file, 'r') as file:
            data = json.load(file)

        config = Config.load_from_dict(data)

        return config
    
    @staticmethod
    def load_from_dict(data: dict):
        return Config(parameters=data['parameters'], prompts=data['prompts'])

    def get_parameter_combinations(self, callback=None):
        enumerated_prompts = [{'_id': f'prompt_{prompt_id:02d}', 'prompt': prompt} for prompt_id, prompt in enumerate(self._prompts)]

        # Create enumerated combination, such that each combination has a unique tuple (i0, i1, i2, ...)
        #enumerated_parameters = [[(i,y) for i,y in enumerate(x)] for x in [enumerated_prompts] + self._parameters]
        enumerated_parameters = [enumerated_prompts] + self._parameters

        num_combinations = self.get_num_combinations()
        if callback:
            keep_running = callback(0, num_combinations)
        else:
            keep_running = True

        for i, combination in enumerate(itertools.product(*enumerated_parameters)):
            yield ParameterCombination(combination)
            if callback:
                keep_running = callback(i+1, num_combinations)
                if keep_running is False:
                    break

    def get_parameter_combination(self, prompt_id, values):
        # FIXME: remove the "enumerated" prefix elsewhere, as it is not needed anymore.
        enumerated_values = [{'_id': f'prompt_{prompt_id:02d}', 'prompt': self._prompts[prompt_id]}] + [values]
        return ParameterCombination(enumerated_values)

    def get_num_combinations(self):
        # Calculate multiplication of all parameter lengths
        num_combinations = len(self._prompts)
        for parameter in self._parameters:
            num_combinations *= len(parameter)
        return num_combinations
    

    @property
    def json(self):
        return {
            'parameters': self._parameters,
            'prompts': self._prompts,
        }

class ParameterCombination:
    def __init__(self, combination: list):
        prompt_arguments = {}  # Arguments used in the prompt expansion
        prompt_arguments_masked = {}  # Arguments used in the prompt expansion, but masked when an _id is present

        for argument in combination:
            values = {k:v for k,v in argument.items() if not k.startswith('_')}
            id = argument.get('_id', None)
            if not id:
                prompt_arguments_masked.update(values)
            else:
                prompt_arguments_masked.update({k:id for k,v in values.items()})



            prompt_arguments.update(values)

        try:
            self._prompt_content = prompt_arguments['prompt'].format(**prompt_arguments)
            self._missing_argument = None
        except KeyError as e:
            print(f'Error: Prompt file contains argument "{e}", but it was not found in the input arguments.')
            print(f'Please, check the prompt file and the input arguments.')
            self._prompt_content = None
            self._missing_argument = [str(e)]


        # Calculate non-cryptographic hash of the prompt content
        # sha1 cryptographic hash of the prompt content
        prompt_hash = hashlib.sha1(self._prompt_content.encode()).hexdigest()
        filepath = os.path.join('cache', prompt_hash[:2], prompt_hash)
        print(filepath)

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
    
    def get_result_file(self, result_name: str):
        return os.path.join(self._filepath, f'result_{result_name}.json')

    @property
    def filepath(self):
        return self._filepath


        

def _get_argument_values(argument_file: str) -> list:
    """
    Process the given argument file and return its data as a dictionary.
    This function supports files (.txt, .py, .xlsx, and .csv) or directories.

    Args:
        argument_file (str): The path to the argument file.

    Returns:
        list: A list of dictionaries containing the argument values. For example:
        [
            {'a': 'data1', 'b': 'data2'},
            {'a': 'data3', 'b': 'data4'},
            ...
        ]
        
    Raises:
        FileNotFoundError: If the argument file does not exist.
        
    Notes:
        It accepts the following file formats:
        - .txt: Each line is a value.
        - .py: The module must contain a generate() function that returns the data.
        - .xlsx, .xls or .csv: The data is read from the first sheet.
        - Directory: Each file in the directory is a value.
    """
    if os.path.isfile(argument_file):
        df = None
        if argument_file.endswith('.txt'):
            return _get_data_from_file(argument_file)

        elif argument_file.endswith('.py'):
            # Load the python file as a module and call the generate function to get the data.
            return _get_data_from_module(argument_file)

        elif argument_file.endswith('.xlsx') or argument_file.endswith('.xls') or argument_file.endswith('.csv'):
            return _get_data_from_spreadsheet(argument_file)
        
    elif os.path.isdir(argument_file):
        # Read all files in the directory and return the file contents as a dictionary.
        return _get_data_from_directory(argument_file)

    return {}

def _get_data_from_file(argument_file: str) -> list:
    """
    Read the given text file and return its data as a list of dictionaries.

    Args:
        argument_file (str): The path to the text file.

    Returns:
        list: A list of dictionaries containing the argument values.
    """
    with open(argument_file, 'r') as file:
        data = [x.strip() for x in file.readlines()] # read data stripping \n

    argument_name = Path(argument_file).stem
    df = pd.DataFrame({argument_name: data})
    return df.to_dict("records")

def _get_data_from_spreadsheet(argument_file: str) -> list:
    """
    Read the given spreadsheet file and return its data as a list of dictionaries.

    Args:
        argument_file (str): The path to the spreadsheet file.

    Returns:
        list: A list of dictionaries containing the argument values.
    """
    if argument_file.endswith('.xlsx') or argument_file.endswith('.xls'):
        # Read the excel file and convert it to a dataframe.
        df = pd.read_excel(argument_file)
    elif argument_file.endswith('.csv'):
        # Read the csv file and convert it to a dataframe.
        df = pd.read_csv(argument_file)

    return df.to_dict("records")

def _get_data_from_module(argument_file: str) -> list:
    """
    Load a module from a file and call its generate() function to get data.

    Args:
        argument_file (str): The path to the file containing the module.

    Returns:
        list: The data returned by the generate() function in the module.
    """
    spec = importlib.util.spec_from_file_location('', argument_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = module.generate()

    argument_name = Path(argument_file).stem
    df = pd.DataFrame({argument_name: data})

    return df.to_dict("records")

def _get_data_from_directory(argument_file: str) -> list:
    """
    Read all files in the given directory and return their data as a list of dictionaries.

    Args:
        argument_file (str): The path to the directory.

    Returns:
        list: A list of dictionaries containing the argument values.
    """
    argument_name = Path(argument_file).stem
    data = [
        {
            '_id': f,
            argument_name: Path(argument_file, f).read_text()
        }
        for f in os.listdir(argument_file)
        if not f.startswith('_')
    ]

    return data
