import pandas as pd

import importlib.util
import json
import os


def load_modules(paths):
    """
    Load all available analysis modules.
    """

    analyse_functions = {}
    
    # Read all modules in the directories
    paths = [path for path in paths if os.path.exists(path)]
    paths.append(os.path.dirname(__file__))
    candidate_modules = [os.path.join(path, file) for path in paths for file in os.listdir(path) if file.endswith('.py') and file not in ['__init__.py']]
    candidate_modules.remove(__file__)

    # list all modules loaded from the llms package. Load it dynamically
    modules = {}
    for module_file in candidate_modules:  # FIXME duplicated code
        module_name = os.path.basename(module_file).split('.')[0]
        print(f'Loading {module_name}')
        spec = importlib.util.spec_from_file_location(module_name, module_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, 'analyse_info'):
            info = module.analyse_info
            print(f'Warning: Module {module_name} does not have an analyse_info dictionary. Skipping.')
        if not hasattr(module, 'analyse'):
            print(f'Warning: Module {module_name} does not have an analyse function. Skipping.')
            continue
        
        name = info.get('name', module_name)
        description = info.get('description', 'No description provided')

        print(f'Loading module: {name} - {description}')
        analyse_functions[name] = {
            'description': description,
            'llm_modules': info.get('llm_modules', None),
            'analyse': module.analyse,
            'reduce': module.reduce if hasattr(module, 'reduce') else None,
            }

    return analyse_functions


def analyse_results(config, output_dir, result_name, analyse_functions):
    # Global Analysis
    result_found = False
    elapsed_time = 0

    combinations = config.get_parameter_combinations()
    for argument_combination in combinations:
        #prompt_file = os.path.join(output_dir, argument_combination.prompt_file)
        result_file = os.path.join(output_dir, argument_combination.get_result_file(result_name))

        if os.path.isfile(result_file):
            with open(result_file, 'r', encoding='utf-8') as file:
                output = json.load(file)

                elapsed_time += output['elapsed_time']

            result_found = True

    # We only analyse if there is any result file
    if not result_found:
        print('No result file found. Skipping analysis.')
        return {}

    analysis_dir = os.path.join(output_dir, 'analysis')
    os.makedirs(analysis_dir, exist_ok=True)

    analysis_results = {}
    for module_name, analyse_function in analyse_functions.items():
        print(f'Analysing with {module_name}')
        analysis = []
        for argument_combination in config.get_parameter_combinations():
            prompt_file = os.path.join(output_dir, argument_combination.prompt_file)
            result_file = os.path.join(output_dir, argument_combination.get_result_file(result_name))
            #base_dir = os.path.join(output_dir, argument_combination.filepath)
            #result_file = os.path.join(base_dir, 'result_gpt.json')

            #base_dir = os.path.join(output_dir, *argument_combination._filepath)
            #result_file = os.path.join(base_dir, 'result_gpt.json')
            if not os.path.isfile(result_file):
                continue

            with open(result_file, 'r', encoding='utf-8') as file:
                output = json.load(file)

                response = output['response']

                r = analyse_function['analyse'](response)
                if r is not None:
                    if not isinstance(r, list):
                        r = [r]
                    # Check if every item in the list has a strict format like {"respose": <list of dictionaries>}
                    if all(isinstance(x, dict) for x in r) and all(len(x) == 1 for x in r):
                        # possible keys
                        possible_keys = {"response", "list", "data", "result", "results", "output"}

                        # Check if the key is in the dictionary and the value is a list in every item
                        if all(list(x.keys())[0] in possible_keys and isinstance(list(x.values())[0], list) for x in r):
                            r = [y for x in r for y in list(x.values())[0]]

                    for x in r:
                        x.update({f'input_{k}':v for k,v in argument_combination._prompt_arguments_masked.items()})
                    analysis += r

        #print(analysis)
        if analyse_function['reduce'] and analysis:
            aggregated_response = analyse_function['reduce'](analysis)
            if not isinstance(aggregated_response, list):
                aggregated_response = [aggregated_response]
        else:
            aggregated_response = analysis

        if isinstance(aggregated_response, list):
            analysis_results[module_name] = aggregated_response
            #df = pd.DataFrame(aggregated_response)
            #df.to_excel(os.path.join(analysis_dir, f'{module_name}.xlsx'), index=False)


    print(f'Elapsed LLM time: {elapsed_time:.2f} seconds')
    return analysis_results