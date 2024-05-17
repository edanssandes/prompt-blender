import json
import os
import time
import importlib.util

from prompt_blender import info

def load_modules(paths):
    """
    Load all available LLM modules.
    """

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

        if not hasattr(module, 'exec'):
            continue

        if not hasattr(module, 'module_info'):
            module.module_info = {'name': module_name, 'description': 'No description available'}

        modules[module_name] = module

    return modules



def execute_llm(llm_module, module_args, config, output_dir, result_name, recreate=False, progress_callback=None, max_cost=0):
    """
    Executes the LLM (Language Model) with the given arguments and output files.

    Args:
        args (Namespace): The command-line arguments.
        output_files (list): A list of tuples containing the prompt file path and corresponding reference values.

    Returns:
        None
    """

    if module_args is None:
        module_args = {}

    llm_module.exec_init()

    total_cost = 0

    def callback(i, num_combinations):
        if progress_callback:
            over_budget = False

            if i == num_combinations:
                description = 'Execution done'
            else:
                description = f"Execution Cost: ${total_cost:.2f}/{max_cost:.2f}"

                if max_cost:
                    if total_cost >= max_cost:
                        # Unicode error for overbudget
                        description += "❌ (over budget)"
                        over_budget = True
                    elif total_cost > max_cost*0.90:
                        # Unicode warning
                        description += "⚠️"

            keep_running = progress_callback(i, num_combinations, description=description)
            x = keep_running and (not over_budget)
            print(x)
            return x
        else:
            return True

    # Define the number of consumers
    num_consumers = 4

    # latest timestamp. This will be used to determine the file name of the output file.
    # If we are reusing all the cached files, the latest timestamp will be the same across all the runs.
    max_timestamp = ''  

    # TODO parallel execution
    for argument_combination in config.get_parameter_combinations(callback):
        output = _execute_inner(llm_module, module_args, output_dir, result_name, recreate, argument_combination)
        max_timestamp = max(max_timestamp, output['timestamp'])

    llm_module.exec_close()

    return max_timestamp

def _execute_inner(llm_module, module_args, output_dir, result_name, recreate, argument_combination):
    prompt_file = os.path.join(output_dir, argument_combination.prompt_file)
    result_file = os.path.join(output_dir, argument_combination.get_result_file(result_name))
    with open(prompt_file, 'r') as file:
        prompt_content = file.read()

    if not recreate and os.path.exists(result_file):
        # Read the result file
        with open(result_file, 'r') as file:
            output = json.load(file)
        
        # Check if the prompt file is the same
        if output['prompt'] != prompt_content:
            print(f'{prompt_file}: prompt file has changed')
            recreate = True
            print(f'{prompt_file}: already processed')
        else:
            return output
            


    print(f'{prompt_file}: processing')
    t0 = time.time()
    response = llm_module.exec(prompt_content, **module_args)
    t1 = time.time()
    #timestamp = pd.Timestamp.now().strftime("%Y%m%d%H%M%S")
    # UTC timestamp
    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())

    # Remove sensitive arguments from the output
    module_args_public = {k: v for k, v in module_args.items() if not k.startswith('_')}  # FIXME duplicated code

    output = {
            'params': argument_combination._prompt_arguments_masked,
            'prompt': prompt_content,
            'module_name': llm_module.__name__,
            'module_args': module_args_public,
            'response': response['response'],
            'cost': response.get('cost', None),
            'elapsed_time': t1 - t0,
            'timestamp': timestamp,
            'app_version': info.__version__,
        }
    with open(result_file, 'w') as file:
        json.dump(output, file)

    return output
