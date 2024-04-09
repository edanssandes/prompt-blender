import pandas as pd
import importlib.util
import os
from pathlib import Path



def expand_arguments(arguments: dict):
    """
    Expand the given arguments to a list of tuples containing the argument name and its values.
    """
    #print(arguments)
    expanded_arguments = [
        _get_argument_values(k, arg).items()   # Convert dictionary to a list of tuples (index, value)
        for k, arg in arguments.items()
    ]

    return expanded_arguments


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
    return data


def _get_argument_values(argument_name: str, argument_file: str) -> dict:
    """
    Process the given argument file and return its data as a dictionary.
    This function supports files (.txt, .py, .xlsx, and .csv) or directories.

    Args:
        argument_name (str): The name of the argument.
        argument_file (str): The path to the argument file.

    Returns:
        dict: A dictionary containing the processed data from the argument file. For example:
        {
            0: {'argument_name': 'value1'},
            1: {'argument_name': 'value2'},
            ...
        }

        If the argument_file is a directory, the dictionary will contain the file names as keys and the file contents as values.
        If the argument_file is a spreedsheet (.xlsx, .xls, or .csv), the dictionary will contain the data from the spreedsheet (multiple columns are supported, 
        the keys will be the column names) as values.
        If the argument_file is a text file (.txt), the dictionary will contain the line numbers as keys and the line content as values.
        If the argument_file is a python file (.py), the module will return a list of values. Then, the dictionary will contain the list index as keys and the list content as values.
    """
    if os.path.isfile(argument_file):
        df = None
        if argument_file.endswith('.txt'):
            # Read the text file and convert it to a dataframe.
            with open(argument_file, 'r') as file:
                data = [x.strip() for x in file.readlines()] # read data stripping \n

            df = pd.DataFrame({argument_name: data})
        elif argument_file.endswith('.py'):
            # Load the python file as a module and call the generate function to get the data.
            data = _get_data_from_module(argument_file)

            df = pd.DataFrame({argument_name: data})
        elif argument_file.endswith('.xlsx') or argument_file.endswith('.xls'):
            # Read the excel file and convert it to a dataframe.
            df = pd.read_excel(argument_file)
        elif argument_file.endswith('.csv'):
            # Read the csv file and convert it to a dataframe.
            df = pd.read_csv(argument_file)

        if df is not None:
            # Convert the dataframe to a dictionary, where the index is the key.
            return df.to_dict("index")
    elif os.path.isdir(argument_file):
        # Read all files in the directory and return the file contents as a dictionary.
        return {
            Path(argument_file, f): {
                argument_name: Path(argument_file, f).read_text()
            }
            for f in os.listdir(argument_file)
            if not f.startswith('_')
        }

    return {}