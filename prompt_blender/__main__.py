import argparse
import os
import json
import importlib.util
import pandas as pd
import time

from prompt_blender.arguments import expand_arguments
from prompt_blender.blend import blend_prompt
from prompt_blender.llms import chatgpt, chatgpt_manual
from prompt_blender.analysis import gpt_cost, gpt_json



def execute_llm(args, output_files):
    """
    Executes the LLM (Language Model) with the given arguments and output files.

    Args:
        args (Namespace): The command-line arguments.
        output_files (list): A list of tuples containing the prompt file path and corresponding reference values.

    Returns:
        None
    """

    if args.gpt_manual_ui:
        llm_module = chatgpt_manual
    else:
        llm_module = chatgpt
    llm_module.exec_init()
    gpt_args = dict(arg.split('=') for arg in args.gpt_args) if args.gpt_args else {}
    if 'n' in gpt_args:
        gpt_args['n'] = int(gpt_args['n'])
        if gpt_args['n'] > 100:
            exit('n must be less than 100')

    for prompt_file, refs_values in output_files:
        base_dir = os.path.dirname(prompt_file)
        result_file = os.path.join(base_dir, 'result_gpt.json')
        if not args.recreate and os.path.exists(result_file):
            print(f'{prompt_file}: already processed')
            continue

        with open(prompt_file, 'r') as file:
            prompt_content = file.read()

        print(f'{prompt_file}: processing')
        t0 = time.time()
        response = llm_module.exec(prompt_content, args.gpt_model, gpt_args, args.gpt_json)
        t1 = time.time()
        
        output = {
            'params': refs_values,
            'prompt': prompt_content,
            'gpt_model': args.gpt_model,
            'gpt_args': gpt_args,
            'gpt_response': response,
            'elapsed_time': t1 - t0,
        }
        with open(result_file, 'w') as file:
            json.dump(output, file)
        
        #print(response)
    llm_module.exec_close()


def analyse_results(args, output_files, analysis_dir):
    # Global Analysis
    result_found = False
    elapsed_time = 0
    for prompt_file, refs_values in output_files:
        result_file = os.path.join(os.path.dirname(prompt_file), 'result_gpt.json')
        if os.path.isfile(result_file):
            with open(result_file, 'r') as file:
                output = json.load(file)

                elapsed_time += output['elapsed_time']

            result_found = True

    # We only analyse if there is any result file
    if not result_found:
        print('No result file found. Skipping analysis.')
        return

    analyse_functions = {}
    os.makedirs(analysis_dir, exist_ok=True)

    # Load modules from args.analyse
    for analyse_module in args.analyse:
        module_name = os.path.basename(analyse_module).split('.')[0]
        print(f'Loading {module_name}')
        spec = importlib.util.spec_from_file_location(module_name, analyse_module)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        analyse_functions[module_name] = {
            'analyse': module.analyse,
            'reduce': module.reduce if hasattr(module, 'reduce') else None,
            }

    for module_name, analyse_function in analyse_functions.items():
        print(f'Analysing with {module_name}')
        analysis = []
        for prompt_file, refs_values in output_files:
            #print(f'{prompt_file}: analysing')
            result_file = os.path.join(os.path.dirname(prompt_file), 'result_gpt.json')
            if not os.path.isfile(result_file):
                continue

            with open(result_file, 'r') as file:
                output = json.load(file)

                response = output['gpt_response']

                r = analyse_function['analyse'](response)
                if not isinstance(r, list):
                    r = [r]
                for x in r:
                    x.update(refs_values)
                analysis += r

        #print(analysis)
        if analyse_function['reduce'] and analysis:
            aggregated_response = analyse_function['reduce'](analysis) 
            if not isinstance(aggregated_response, list):
                aggregated_response = [aggregated_response]            
        else:
            aggregated_response = analysis

        if isinstance(aggregated_response, list):
            df = pd.DataFrame(aggregated_response)
            df.to_excel(os.path.join(analysis_dir, f'{module_name}.xlsx'), index=False)

    print(f'Elapsed LLM time: {elapsed_time:.2f} seconds')



parser = argparse.ArgumentParser()

parser.add_argument('--job', type=str, help='Path to the job directory', default=None)

parser.add_argument('--prompt-file', type=str, help='Path to the prompt file')
parser.add_argument('--args', nargs='+', help='List of file or directory arguments')
parser.add_argument('--output-dir', type=str, help='Path to the output directory')
parser.add_argument('--analysis-dir', type=str, help='Path to the analysis directory')

# argument for execution: --exec
parser.add_argument('--exec', action='store_true', help='Execute LLM with the generated prompts')
parser.add_argument('--recreate', action='store_true', help='Recreate the output files')

# argumentos for chatgpt: --model gpt-3.5-turbo-0125 --api-key-file secret.key --args temperature=0.5 top_p=0.9
parser.add_argument('--gpt-model', type=str, help='Model name for chatgpt', default='gpt-3.5-turbo-0125')
parser.add_argument('--gpt-args', nargs='+', help='List of arguments for chatgpt in the form key=value')
parser.add_argument('--gpt-json', action='store_true', help='Return the response in json format', default=True)
parser.add_argument('--gpt-manual-ui', action='store_true', help='Use manual UI for chatgpt. Same as --gpt-model=gpt-manual-ui', default=False)

# You can use many times the --analyse argument to analyse the output files
parser.add_argument('--analyse', type=str, nargs='+', help='Python file used to analyse the output files. The file must contains a function called analyse(refs_values, content)')

args = parser.parse_args()

# If job is not defined, then prompt-file, args, output-dir and analysis-dir must be defined
if not args.job:
    # If any of the arguments is not defined, then exit
    if not args.prompt_file or not args.args or not args.output_dir or not args.analysis_dir:
        #show help
        parser.print_help()
        print('\n')
        exit('Error: If job is not defined, then --prompt-file, --args, --output-dir and --analysis-dir must be defined')

job_dir = args.job

if job_dir:
    input_dir = os.path.join(job_dir, 'input')
    if os.path.isdir(input_dir):
        arguments = {os.path.splitext(name)[0]: os.path.join(input_dir, name) for name in sorted(os.listdir(input_dir)) if not name.startswith('_')}
    else:
        arguments = {}
    prompt_file = os.path.join(job_dir, 'prompt.txt')
    output_dir = os.path.join(job_dir, 'output')
    analysis_dir = os.path.join(job_dir, 'analysis')

if args.args:
    arguments = args.args

if args.prompt_file:
    prompt_file = args.prompt_file

if args.output_dir:
    output_dir = args.output_dir

if args.analysis_dir:
    analysis_dir = args.analysis_dir

if args.gpt_manual_ui:
    args.gpt_model = 'gpt-manual-ui'

if args.analyse is None:
    args.analyse = []
   
print('Expanding arguments...')
expanded_arguments = expand_arguments(arguments)
for k, v in zip(arguments.keys(), expanded_arguments):
    print(f'{k:>10s}: {len(v)} values')


print('Generating prompts...', end='')
output_files = blend_prompt(prompt_file, expanded_arguments, output_dir)
print(f' Done: {len(output_files)} files generated.')



if args.exec:
    execute_llm(args, output_files)

args.analyse += [gpt_cost.__file__]
if args.gpt_json:
    args.analyse += [gpt_json.__file__]

if args.analyse:
    analyse_results(args, output_files, analysis_dir)
    
print('Done')