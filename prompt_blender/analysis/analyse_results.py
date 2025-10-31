import io
import zipfile
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


def analyse_results(run, config, output_dir, analyse_functions):
    # Global Analysis
    result_found = False
    elapsed_time = 0
    total_cost = 0

    run_hash = run['run_hash']

    combinations = config.get_parameter_combinations()
    for argument_combination in combinations:
        #prompt_file = os.path.join(output_dir, argument_combination.prompt_file)
        result_file = os.path.join(output_dir, argument_combination.get_result_file(run_hash))

        if os.path.isfile(result_file):
            with open(result_file, 'r', encoding='utf-8') as file:
                output = json.load(file)

                elapsed_time += output.get('elapsed_time', 0)
                total_cost += output.get('cost', 0)

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
            result_file = os.path.join(output_dir, argument_combination.get_result_file(run_hash))
            #base_dir = os.path.join(output_dir, argument_combination.filepath)
            #result_file = os.path.join(base_dir, 'result_gpt.json')

            #base_dir = os.path.join(output_dir, *argument_combination._filepath)
            #result_file = os.path.join(base_dir, 'result_gpt.json')
            if not os.path.isfile(result_file):
                continue

            with open(result_file, 'r', encoding='utf-8') as file:
                output = json.load(file)

                response = output['response']
                timestamp = output['timestamp']

                r = analyse_function['analyse'](response, timestamp)
                if r is not None:
                    if not isinstance(r, list):
                        r = [r]

                    # Extract _extra field if present. This is nedded to check if there is a single item (possible key) in the list
                    extras = [x.pop('_extra', None) for x in r]
                    timestamps = [x.pop('_timestamp', None) for x in r]

                    # Check if every item in the list has a strict format like {"respose": <list of dictionaries>}
                    if all(isinstance(x, dict) for x in r) and all(len(x) == 1 for x in r):
                        # possible keys
                        possible_keys = {"response", "list", "data", "result", "results", "output"}

                        # Check if the key is in the dictionary and the value is a list in every item
                        if all(list(x.keys())[0] in possible_keys and isinstance(list(x.values())[0], list) for x in r):
                            new_r = []
                            for x, timestamp, extra in zip(r, timestamps, extras):
                                # Flatten the list of dictionaries
                                l = list(x.values())[0]

                                if not l:
                                    l = [{}]  # Add an empty dictionary to ensure a row is created

                                # Restore extra and timestamp fields if they exist
                                if extra:
                                    l = [dict(item, **extra) for item in l]
                                if timestamp:
                                    l = [dict(item, _timestamp=timestamp) for item in l]
                                new_r.extend(l)
                                
                            r = new_r

                    # add the input arguments to the response
                    for x in r:
                        x.update({f'input_{k}':v for k,v in argument_combination._prompt_arguments_masked.items()})

                    # Add the extra and timestamp fields back to the dictionaries, if they exist
                    for x, extra, timestamp in zip(r, extras, timestamps):
                        if extra:
                            x.update(extra)
                        if timestamp:
                            x.update({'_timestamp': timestamp})
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
    if total_cost:
        print(f'Total cost: US$ {total_cost:.5f}')

    analysis_results['info'] = [{
        'elapsed_time': elapsed_time,
        'total_cost': total_cost,
    }]

    return analysis_results


def save_analysis_results(filename, output_dir, analysis_results, data, run_args):
    # Merge all analysis results into a single dictionary.
    merged_analysis_results = _merge_analysis_results(data, analysis_results, run_args)

    # Create the final zip file
    _save_result_file(filename, output_dir, merged_analysis_results, data, run_args)



def _merge_analysis_results(config, analysis_results, run_args):
    # Merge all analysis results into a single dictionary. Parameter "_run" will be added to each result
    merged_analysis_results = {}
    for run_name, analysis in analysis_results.items():
        for module_name, results in analysis.items():
            if module_name not in merged_analysis_results:
                merged_analysis_results[module_name] = []
            for result in results:
                result['_run'] = run_name
                merged_analysis_results[module_name].append(result)

    # Include all prompts
    merged_analysis_results['prompts'] = []
    merged_analysis_results['runs'] = []

    for k,v in config.enabled_prompts.items():
        merged_analysis_results['prompts'].append({
            'Prompt Name': k,
            'Template': v
        })
    for name, run in run_args.items():
        merged_analysis_results['runs'].append({
            'Run Name': name,
            'Module Name': run['module_name'],
            'Module ID': run['module_info'].get('id', 'Unknown'),
            'Run Hash': run['run_hash'],
            'Module Description': run['module_info'].get('description', 'Unknown'),
            'Module Version': run['module_info'].get('version', 'Unknown'),
            'Arguments': json.dumps(run['args'], indent=4)
        })

    return merged_analysis_results


def _save_result_file(filename, output_dir, merged_analysis_results, data, run_args):
    with zipfile.ZipFile(filename, 'w') as zipf:
        byteio = io.BytesIO()
        with pd.ExcelWriter(byteio, engine="xlsxwriter") as writer:
            #for run, analysis in merged_analysis_results.items():  # FIXME
                for module_name, results in merged_analysis_results.items():
                    if results:
                        df = pd.DataFrame(results)
                        df.to_excel(writer, sheet_name=module_name, index=False)

        byteio.seek(0)
        zipf.writestr(f'result.xlsx', byteio.read())


        # Add the config file to the zip
        with io.StringIO() as config_io:
            data.save_to_fp(config_io)
            zipf.writestr('config.pbp', config_io.getvalue())

        #zipf.writestr('execution.json', json.dumps({'module': llm_module.__name__, 'args': module_args_public}))

        # This set keeps track of the result files that are already in the zip
        result_files = set()

        # Add the prompt files and result files to the zip
        for argument_combination in data.get_parameter_combinations():
            prompt_file = os.path.join(output_dir, argument_combination.prompt_file)
            zipf.write(prompt_file, os.path.relpath(prompt_file, output_dir))
            for run in run_args.values():
                result_file = os.path.join(output_dir, argument_combination.get_result_file(run['run_hash']))

                if result_file not in result_files:
                    full_result_file = os.path.join(output_dir, result_file)
                    if os.path.exists(full_result_file):
                        zipf.write(full_result_file, os.path.relpath(full_result_file, output_dir))
                        result_files.add(result_file)
                    else:
                        print(f"Warning: Result file {result_file} not found")
                    result_files.add(result_file)