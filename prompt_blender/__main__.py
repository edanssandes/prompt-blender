import argparse
import os
import sys

from prompt_blender.analysis.analyse_results import analyse_results
from prompt_blender.arguments import Config
from prompt_blender.blend import blend_prompt
from prompt_blender.llms.execute_llm import execute_llm
from prompt_blender.analysis import gpt_cost, gpt_json

from prompt_blender.llms import chatgpt, chatgpt_manual

parser = argparse.ArgumentParser()

parser.add_argument('--job-dir', type=str, help='Path to the job directory', default=None)
parser.add_argument('--job-file', type=str, help='Path to the json file', default=None)

parser.add_argument('--prompt-file', type=str, help='Path to the prompt file')
parser.add_argument('--parameter-files', nargs='+', help='List of file or directory parameters')
parser.add_argument('--output-dir', type=str, help='Path to the output directory')

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

parser.add_argument('--gui', action='store_true', help='Show GUI for the analysis', default=False)


args = parser.parse_args()

if args.gui or len(sys.argv) == 1:
    from prompt_blender.gui import main_wx
    main_wx.run()
    exit()

# If job is not defined, then prompt-file, args, output-dir and analysis-dir must be defined
if not args.job_dir and not args.job_file:
    # If any of the arguments is not defined, then exit
    if not args.prompt_file or not args.args or not args.output_dir:
        #show help
        parser.print_help()
        print('\n')
        exit('Error: If job is not defined, then --prompt-file, --args, --output-dir and --analysis-dir must be defined')

job_dir = args.job_dir

if job_dir:
    output_dir = os.path.join(job_dir, 'output')


if args.parameter_files:
    parameter_files = args.parameter_files

if args.prompt_file:
    prompt_file = args.prompt_file

if args.output_dir:
    output_dir = args.output_dir

if args.gpt_manual_ui:
    args.gpt_model = 'gpt-manual-ui'

if args.analyse is None:
    args.analyse = []
   
   
print('Expanding job configuration...')
if args.job_file:
    config = Config.load_from_json(args.job_file)
elif args.job_dir:
    config = Config.load_from_dir(args.job_dir)
else:
    config = Config.load_from_parameters(output_dir)

print(config.json)


print('Generating prompts...', end='')
output_files = blend_prompt(config, output_dir)
print(f' Done: {len(output_files)} files generated.')



if args.exec:
    if args.gpt_manual_ui:
        llm_module = chatgpt_manual
    else:
        llm_module = chatgpt

    module_args = llm_module.get_args(args)
    execute_llm(llm_module, module_args, config, output_dir, args.recreate)

args.analyse += [gpt_cost.__file__]
if args.gpt_json:
    args.analyse += [gpt_json.__file__]

if args.analyse:
    analyse_results(args, output_files, output_dir)
    
print('Done')