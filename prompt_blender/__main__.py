import argparse
import os
import pandas as pd

from prompt_blender.blend import blend_prompt
from prompt_blender.llms import execute_llm
from prompt_blender.gui.preferences import Preferences
from prompt_blender.gui.model import Model

from prompt_blender.gui import main_wx

from prompt_blender.analysis import analyse_results


parser = argparse.ArgumentParser()
parser.add_argument('--config', type=str, help='Path to the configuration file (.pbp)')
parser.add_argument('--preferences', type=str, help='Path to the preferences file (.config)')
parser.add_argument('--merge', type=str, nargs='*', help='Merge parameters from CSV file(s) in format: parameter=file.csv')
parser.add_argument('--output', type=str, help='Path to the output file')


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
        param_name, csv_file = merge_param.split('=', 1)
        if config_data.get_parameter(param_name) is None:
            raise ValueError(f"Parameter '{param_name}' not found in configuration. You can only merge existing parameters.")
        config_data.remove_param(param_name)
        if os.path.isdir(csv_file):
            config_data.add_table_from_directory(directory_path=csv_file, variable=param_name)
            print(f"Merged parameter '{param_name}' from directory: '{csv_file}'")
        elif os.path.isfile(csv_file):
            config_data.add_table_from_file(file_path=csv_file, variable=param_name)
            print(f"Merged parameter '{param_name}' from file:'{csv_file}'")
        else:
            raise FileNotFoundError(f"CSV file or directory not found: {csv_file}")


def main():
    args = parser.parse_args()

    gui = (args.config is None)

    # GUI mode
    if gui:
        main_wx.run()
        exit()

    # Non-GUI execution
    if not os.path.exists(args.config):
        exit(f'Error: Configuration file not found: {args.config}')

    print('Expanding job configuration...')
    config = Model.create_from_file(args.config)

    # Load preferences from config file
    preferences = Preferences.load_from_file(args.preferences)

    # Apply merge(s) if specified
    if args.merge:
        merge_csv_parameters(config, args.merge)

    # Set output zip file
    if args.output:
        output_zip = args.output
    else:
        config_dir = os.path.dirname(os.path.abspath(args.config))
        config_name = os.path.splitext(os.path.basename(args.config))[0]
        output_zip = os.path.join(config_dir, f"{config_name}_results.zip")

    output_dir = preferences.cache_dir


    analyse_functions = analyse_results.load_modules(["./plugins"])
    llm_modules = execute_llm.load_modules(["./plugins"])

    print('Generating prompts...', end='')
    output_files = blend_prompt(config, output_dir)
    print(f' Done: {len(output_files)} files generated.')

    analysis_results = {}
    max_cost = preferences.max_cost
    cache_timeout = None

    run_args = config.get_run_args(llm_modules)

    for name, run in run_args.items():
        timestamp = execute_llm.execute_llm(run, config, output_dir, progress_callback=None, cache_timeout=cache_timeout, max_cost=max_cost)
        ret = analyse_results.analyse_results(run, config, output_dir, analyse_functions)
        analysis_results[name] = ret

    merged_analysis_results = main_wx.merge_analysis_results(config, analysis_results, run_args)

    print(f'Saving results to {output_zip}...')
    main_wx.save_result_file(output_zip, output_dir, merged_analysis_results, config, run_args)
    print('Done')


if __name__ == "__main__":
    main()