import re
import os



def blend_prompt(config, cache_dir, progress_callback=None):
    """
    Merge prompt file with all argument combinations and create new prompt files in the output directory.

    Args:
        config (dict): A dictionary containing the prompt content and the arguments to be merged.
        output_dir (str): The output directory where the prompt files will be saved.

    Returns:
        list: List of tuples containing the filename and corresponding parameters used in the prompt.
    """
    print(config)

    #prompt_content = config._prompt

    # Create a list to store the file information to be returned.
    files = []

    # Check for errors in the prompt content.
    for argument_combination in config.get_parameter_combinations():
        if argument_combination.missing_argument:
            print(f'Error: Prompt file is missing the following arguments: {argument_combination.missing_argument}')
            print(f'Please, check the prompt file and the input arguments.')
            exit(1)

    def callback(i, num_combinations):
        if progress_callback:
            if i == num_combinations:
                description = 'Blending done'
            else:
                description = 'Blending prompts...'

            return progress_callback(i, num_combinations, description=description)
        else:
            return True

    print(f'Creating prompt files in {cache_dir}...')
    for argument_combination in config.get_parameter_combinations(callback):

        # Join the file path and create the directory if it does not exist.
        filepath = os.path.join(cache_dir, argument_combination.filepath)
        os.makedirs(filepath, exist_ok=True)

        # Create the prompt file with the expanded arguments.
        filename = os.path.join(filepath, 'prompt.txt')


        # Write the prompt content to the file.
        with open(filename, 'w', encoding='utf-8') as file:
            prompt_content = argument_combination.prompt_content
            file.write(prompt_content)

        # Add the filename and reference values to the list of files to be returned.
        files.append((filename, argument_combination._prompt_arguments))

        print(f'  {filename}')
        #print(filename, refs_values)

    #print(files)
    return files
