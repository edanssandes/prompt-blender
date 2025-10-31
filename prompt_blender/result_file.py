import pandas as pd


import io
import os
import zipfile
import json


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


def save_analysis_results(filename, output_dir, analysis_results, data, run_args):
    # Merge all analysis results into a single dictionary.
    merged_analysis_results = _merge_analysis_results(data, analysis_results, run_args)

    # Create the final zip file
    _save_result_file(filename, output_dir, merged_analysis_results, data, run_args)


def read_result_file(filename):
    analysis_results = {}
    with zipfile.ZipFile(filename, 'r') as zipf:
        with zipf.open('result.xlsx') as xlsx_file:
            xls = pd.ExcelFile(xlsx_file)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                analysis_results[sheet_name] = df.to_dict(orient='records')
    return analysis_results