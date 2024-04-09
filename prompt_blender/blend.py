import re
import os
import itertools
from pathlib import Path

from prompt_blender.arguments import _get_argument_values


def read_prompt(prompt_file: str):
    """
    Read the contents of a prompt file.

    Args:
        prompt_file (str): The path to the prompt file.

    Returns:
        str: The contents of the prompt file.
    """
    with open(prompt_file, 'r') as file:
        return file.read()


def blend_prompt(prompt_file, argument_values, output_dir):
    """
    Merge prompt file with all argument combinations and create new prompt files in the output directory.

    Args:
        prompt_file (str): The prompt file.
        arguments (dict): Dictionary of argument files.
        output_dir (str): The output directory.

    Returns:
        list: List of tuples containing the filename and corresponding reference values.
        The reference values are used to identify the arguments used in the prompt.
        When the argument points to a txt file, the reference value is the filename. Otherwise, it is the argument index (e.g. line number).
    """
    with open(prompt_file, 'r') as file:
        prompt_content = file.read()

    #argument_combinations = generate_argument_combinations(arguments)
    argument_combinations = itertools.product(*argument_values)

    # Create a list to store the file information to be returned.
    files = []

    #print(output_dir)
    for argument_combination in argument_combinations:

        refs_values = {}  # Reference values used to identify the arguments used in the prompt
        prompt_arguments = {}  # Arguments used in the prompt expansion
        filepath = [output_dir]  # File path to save the prompt file in the output directory

        for x, v in argument_combination:
            prompt_arguments.update(v)
            if isinstance(x, int):
                # If the argument is an integer, use it as the reference value with leading zeros.
                filepath.append(f'{x:04d}')

                # The reference value will be updated with all the argument values of that combination.
                # Recall that the argument may contain multiple values (e.g., a row from a spreadsheet) ou a single value (e.g., a line from a txt file).
                refs_values.update(v)
            elif isinstance(x, Path):
                # If the argument is a Path, use the first word of the filename as the reference value, without the extension.
                filename_without_extension = os.path.splitext(x.name)[0]
                prefix_name = re.split('[\s]', filename_without_extension, maxsplit=1)[0]  # Get the first word
                filepath.append(prefix_name)

                # The reference value is the filename with the extension.
                refs_values.update({k:x.name for k,_ in v.items()})

        # Join the file path and create the directory if it does not exist.
        filepath = os.path.join(*filepath)
        os.makedirs(filepath, exist_ok=True)

        # Create the prompt file with the expanded arguments.
        filename = os.path.join(filepath, 'prompt.txt')

        # Write the prompt content to the file.
        with open(filename, 'w') as file:
            try:
                content = prompt_content.format(**prompt_arguments)
            except KeyError as e:
                print(f'Error: Prompt file contains argument "{e}", but it was not found in the input arguments.')
                print(f'Please, check the prompt file and the input arguments.')
                exit(1)
            file.write(content)

        # Add the filename and reference values to the list of files to be returned.
        files.append((filename, refs_values))
        #print(filename, refs_values)


    return files
