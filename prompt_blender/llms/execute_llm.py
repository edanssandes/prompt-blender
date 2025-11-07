import json
import os
import time
import importlib.util
import copy
import traceback

from prompt_blender import info
from prompt_blender.analysis import gpt_json

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

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            print("*******WARNING*******")
            print(f'Error loading module {module_name}: {e}')
            # dump stack trace
            traceback.print_exc()
            print("*********************")

            continue

        if not hasattr(module, 'exec'):
            print(f'Warning: module {module_name} does not have an exec method.'.format(module_name))
            continue

        if not hasattr(module, 'module_info'):
            module.module_info = {
                'name': module_name, 
                'id': None,
                'description': 'No description available'
            }

        if not 'version' in module.module_info:
            module.module_info['version'] = ''
        module_id = module.module_info.get('id', None)

        if not module_id:
            print(f'Warning: module {module_name} does not have an id.'.format(module_name))
            continue

        modules[module_id] = module

    return modules


def expire_cache(run_args, config, cache_dir, cache_timeout=None, progress_callback=None, combinations=None, error_items_only=False):
    """
    Expire the cache for the given run arguments and configuration.
    
    Args:
        run_args (dict): The run arguments containing the LLM module and other parameters.
        config (ConfigModel): The configuration model containing parameter combinations.
        cache_dir (str): The directory where cache output files are stored.
        cache_timeout (int, optional): The cache timeout in seconds. Defaults to None, meaning no expiration.

    Returns:
        None
    """

    if progress_callback:
        progress_callback(0, 0, description="Loading LLM module...")

    def callback(i, num_combinations):
        if progress_callback:
            description = "Expiring cache..." if i < num_combinations else "Finishing up..."
            return progress_callback(i, num_combinations, description=description)
        else:
            return True

    if combinations is None:
        combinations = config.get_parameter_combinations(callback)

    expired_count = 0
    for argument_combination in combinations:
        result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_args['run_hash']))
        delayed_file = result_file + '.delayed'

        if error_items_only and not is_result_with_error(result_file):
            continue

        #print("EXPIRING", result_file)
        expire_file(cache_timeout, result_file)
        expire_file(cache_timeout, delayed_file)
        expired_count += 1

    if progress_callback:
        progress_callback(0, 0, description="Finishing up...")

    return expired_count

def is_result_with_error(result_file):
    if os.path.exists(result_file):
        with open(result_file, 'r', encoding='utf-8') as file:
            output = json.load(file)
        analysis_results = gpt_json.analyse(output['response'], output['timestamp'])
        
        for r in analysis_results:
            if r.get('_error', None):
                print(r)
                return True
    return False

def expire_file(cache_timeout, file):
    if os.path.exists(file):
        print(file)
        cache_age = time.time() - os.path.getmtime(file)
        if cache_age >= cache_timeout:
            print(f'Expiring cache for {file}')
            os.remove(file)


def execute_llm(run_args, config, cache_dir, cache_timeout=None, progress_callback=None, max_cost=0, gui=False):
    """
    Executes the LLM (Language Model) with the given arguments and output files.
    """
    
    module_args = run_args.get('args', {})
    print('Running module:', run_args['module_name'], 'with args:', module_args)
    print(f'Run Hash: {run_args["run_hash"]}')

    if progress_callback:
        progress_callback(0, 0, description="Loading LLM module...")

    time.sleep(0.75)  # This allows the animation to be shown in the GUI for executions that are too fast (e.g. full cache hits)

    llm_module = run_args['llm_module']

    total_cost = 0

    def callback(i, num_combinations):
        if progress_callback:
            over_budget = False

            if i == num_combinations:
                description = 'Finishing up...'
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

            if total_cost >= max_cost:
                print("Execution cost exceeded the budget. Stopping execution.")
                raise RuntimeError(f"Execution cost exceeded the budget: ${total_cost:.2f} > ${max_cost:.2f}")

            return x
        else:
            return True

    # latest timestamp. This will be used to determine the file name of the output file.
    # If we are reusing all the cached files, the latest timestamp will be the same across all the runs.
    max_timestamp = ''
    module_initialized = False

    # All combinations must sleep at most 2 seconds in total. So, for N combinations:
    # the maximum sleep time per combination is 2 seconds / N
    sleep_time = min(max(2 / config.get_num_combinations(), 0.001), 0.1)

    try:
        for argument_combination in config.get_parameter_combinations(callback):
            output = get_cached_response(run_args, cache_dir, cache_timeout, argument_combination)
            if output is None:
                if not module_initialized:
                    llm_module.exec_init(gui=gui)
                    module_initialized = True
                output = _execute_inner(run_args, cache_dir, argument_combination)
            time.sleep(sleep_time)  # This allows the animation to be shown in the GUI for executions that are too fast (e.g. full cache hits)

            if output:
                max_timestamp = max(max_timestamp, output['timestamp'])
                total_cost += output['cost'] if output.get('cost', None) is not None else 0

        if progress_callback:
            r = progress_callback(0, 0, description="Processing delayed executions...")
            if not r:
                return max_timestamp

        pending = _execute_delayed(run_args, config, cache_dir, llm_module, module_initialized, gui)
        print(pending)

        if pending:
            raise RuntimeError(f"There {('is', 'are')[pending>1]} {pending} pending results in asynchronous execution. Please, run again later to get the final results.")

        if progress_callback:
            progress_callback(0, 0, description="Finishing up...")
    finally:
        if module_initialized:
            llm_module.exec_close()

    return max_timestamp


def get_cached_response(run, cache_dir, cache_timeout, argument_combination):
    """
    Retrieves cached responses for the given run arguments and configuration.
    """
    run_hash = run['run_hash']

    #module_args = dict(run['args']) # Make a copy of the module arguments to avoid modifying the original

    prompt_file = os.path.join(cache_dir, argument_combination.prompt_file)
    result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_hash))
    delayed_file = result_file + '.delayed'

    if os.path.exists(delayed_file):
        return None

    with open(prompt_file, 'r', encoding='utf-8') as file:
        prompt_content = file.read()

    if cache_timeout is None:
        cache_timeout = float('inf')

    if os.path.exists(result_file):
        cache_age = time.time() - os.path.getmtime(result_file)

        if cache_age < cache_timeout:
            # Read the result file
            try:
                with open(result_file, 'r', encoding='utf-8') as file:
                    output = json.load(file)

                # Check if the prompt file is the same
                if output['prompt'] != prompt_content:
                    print(f'{prompt_file}: prompt file has changed')
                else:
                    return output                    
            except json.JSONDecodeError:
                print(f'{result_file}: cache file is corrupted. Deleting it.')
                os.remove(result_file)
            except Exception:
                print(f'{result_file}: cache file is corrupted.')
                raise

    return None



def _execute_inner(run, cache_dir, argument_combination):
    llm_module = run['llm_module']
    run_hash = run['run_hash']

    #module_args = dict(run['args']) # Make a copy of the module arguments to avoid modifying the original

    prompt_file = os.path.join(cache_dir, argument_combination.prompt_file)
    result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_hash))
    delayed_file = result_file + '.delayed'

    if os.path.exists(delayed_file):
        return None

    with open(prompt_file, 'r', encoding='utf-8') as file:
        prompt_content = file.read()

    # Remove sensitive arguments from the output
    module_args_public = {k: v for k, v in run['args'].items() if not k.startswith('_')}  # FIXME duplicated code

    #timestamp = pd.Timestamp.now().strftime("%Y%m%d%H%M%S")
    # UTC timestamp
    timestamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())

    print(f'{prompt_file}: processing')
    t0 = time.time()
    
    args = copy.deepcopy(run['args'])  # creating an deepcopy to avoid the llm_module modifying the original arguments
    response = llm_module.exec(prompt_content, **args)

    output = {
            'params': argument_combination._prompt_arguments_masked,
            'prompt': prompt_content,
            'module_name': llm_module.__name__,
            'module_version': llm_module.module_info.get('version', ''),
            'module_args': module_args_public,
            'timestamp': timestamp,
            'app_name': info.APP_NAME,
            'app_version': info.__version__,
        }

    if 'delayed' in response:
        with open(delayed_file, 'w', encoding='utf-8') as file:
            output['delayed'] = response['delayed']
            json.dump(output, file)

        return None
    
    t1 = time.time()

    output['response'] = response['response']
    output['cost'] = response.get('cost', 0)
    output['elapsed_time'] = t1 - t0

    with open(result_file, 'w', encoding='utf-8') as file:
        json.dump(output, file)

    return output


def _execute_delayed(run_args, config, cache_dir, llm_module, initialized, gui):
    if 'exec_delayed' not in dir(llm_module):
        # If the module does not support delayed execution, return immediately
        return None
    
    old_delayed_data = {}
    delayed_params = {}
    for argument_combination in config.get_parameter_combinations():
        result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_args['run_hash']))
        delayed_file = result_file + '.delayed'
        if os.path.exists(delayed_file):
            with open(delayed_file, 'r', encoding='utf-8') as file:
                data = json.load(file)
                old_delayed_data[argument_combination.prompt_hash] = data
                delayed_params[argument_combination.prompt_hash] = data['delayed']

    if not delayed_params:
        return 0

    if not initialized:
        llm_module.exec_init(gui=gui)
        initialized = True

    new_delayed_data = llm_module.exec_delayed(delayed_params)

    pending = 0
    for argument_combination in config.get_parameter_combinations():
        result_file = os.path.join(cache_dir, argument_combination.get_result_file(run_args['run_hash']))
        delayed_file = result_file + '.delayed'
        if os.path.exists(delayed_file):

            new_info = new_delayed_data.get(argument_combination.prompt_hash, None)


            if new_info is None:
                pending += 1
            elif 'delayed' in new_info:
                pending += 1

                # Save delayed data to file
                with open(delayed_file, 'w', encoding='utf-8') as file:
                    # Update the old delayed data with the new information - only the 'delayed' key. We keep the rest of the data intact
                    old_info = old_delayed_data.get(argument_combination.prompt_hash, {})
                    old_info['delayed'] = new_info['delayed']
                    json.dump(old_info, file)
                print("New delayed data saved to file:", delayed_file)
            else:
                # If the delayed data is not present, we can remove the file
                if os.path.exists(delayed_file):
                    os.remove(delayed_file)

                # Save the new data to the result file
                with open(result_file, 'w', encoding='utf-8') as file:
                    old_info = old_delayed_data.get(argument_combination.prompt_hash, {})
                    new_info = {**old_info, **new_info}
                    json.dump(new_info, file)

    return pending