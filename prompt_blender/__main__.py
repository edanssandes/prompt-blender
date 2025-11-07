import argparse
import os
import pandas as pd

from prompt_blender.blend import blend_prompt
from prompt_blender.llms import execute_llm
from prompt_blender.preferences import Preferences
from prompt_blender.model import Model

from prompt_blender.gui import main_wx

from prompt_blender.analysis import analyse_results
from prompt_blender import result_file


parser = argparse.ArgumentParser()
parser.add_argument('config', nargs='?', default=None, help='Path to the configuration file (.pbp)')
parser.add_argument('--preferences', type=str, help='Path to the preferences file (.config)')
parser.add_argument('--merge', type=str, nargs='*', help='Merge parameters from CSV file(s) in format: parameter=file.csv')
parser.add_argument('--output', type=str, help='Path to the output file')
parser.add_argument('--overwrite', action='store_true', help='Overwrite existing output file without prompt')
parser.add_argument('--dump-results', type=str, help='Path to the result file to dump')
parser.add_argument('--run', action='store_true', help='Run now (non-GUI mode)')
parser.add_argument('--cache-dir', type=str, help='Path to the cache directory. Overrides preferences setting.')

def merge_csv_parameters(config_data, merge_params):
    """
    Merge multiple CSV parameters into config data.
    Args:
        config_data: Dictionary containing the configuration
        merge_params: List of strings in format "parameter_index=file.csv"
    Returns:
        Modified config_data
    """
    for merge_param in merge_params:
        if '=' not in merge_param:
            raise ValueError("--merge parameter must be in format: parameter=file.csv")
        param_name, file_or_dir = merge_param.split('=', 1)
        if config_data.get_parameter(param_name):
            config_data.remove_param(param_name)
        if os.path.isdir(file_or_dir):
            config_data.add_table_from_directory(directory_path=file_or_dir, variable=param_name)
            print(f"Merged parameter '{param_name}' from directory: '{file_or_dir}'")
        elif os.path.isfile(file_or_dir):
            config_data.add_table_from_file(file_path=file_or_dir, variable=param_name)
            print(f"Merged parameter '{param_name}' from file:'{file_or_dir}'")
        else:
            raise FileNotFoundError(f"CSV file or directory not found: {file_or_dir}")


def main():
    args = parser.parse_args()

    if args.dump_results:
        analysis_results = result_file.read_result_file(args.dump_results)
        for module_name, results in analysis_results.items():
            print(f"Results for module: {module_name}")
            df = pd.DataFrame(results)
            print(df)
        exit()

    if args.config and not os.path.exists(args.config):
        exit(f'Error: Configuration file not found: {args.config}')

    if args.config:
        # Load configuration
        model = Model.create_from_file(args.config)

        # Apply merge(s) if specified
        if args.merge:
            merge_csv_parameters(model, args.merge)


    else:
        model = None

    # GUI mode
    if not args.run:
        main_wx.run(model=model)
        exit()
    elif model is None:
        exit('Error: Configuration file must be provided in non-GUI mode.')

    # Non-GUI execution

    # Set output zip file
    if args.output:
        output_zip = args.output
    else:
        config_dir = os.path.dirname(os.path.abspath(args.config))
        config_name = os.path.splitext(os.path.basename(args.config))[0]
        output_zip = os.path.join(config_dir, f"{config_name}_results.zip")

    # Check if output file exists
    if os.path.exists(output_zip) and not args.overwrite:
        exit(f'Error: Output file already exists: {output_zip}. Use --overwrite to overwrite it.')


    # Load preferences from config file
    preferences = Preferences.load_from_file(args.preferences)

    if args.cache_dir:
        cache_dir = args.cache_dir
    else:
        cache_dir = preferences.cache_dir

    analyse_functions = analyse_results.load_modules(["./plugins"])
    llm_modules = execute_llm.load_modules(["./plugins"])

    print('Generating prompts...', end='')
    output_files = blend_prompt(model, cache_dir)
    print(f' Done: {len(output_files)} files generated.')

    analysis_results = {}
    max_cost = 0  # Unlimited
    cache_timeout = None

    run_args = model.get_run_args(llm_modules)

    for name, run in run_args.items():
        execute_llm.execute_llm(run, model, cache_dir, progress_callback=None, cache_timeout=cache_timeout, max_cost=max_cost)
        ret = analyse_results.analyse_results(run, model, cache_dir, analyse_functions)
        analysis_results[name] = ret

    print(f'Saving results to {output_zip}...')
    result_file.save_analysis_results(output_zip, cache_dir, analysis_results, model, run_args)
    print('Done')


if __name__ == "__main__":
    main()