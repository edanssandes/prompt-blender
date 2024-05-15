# PromptBlender

## Overview

PromptBlender is a tool designed to automate the generation, execution, and analysis of prompts for use with language learning models (LLMs). It simplifies the task of creating multiple prompts by automatically filling parameters within a template, generating a Cartesian product of prompts, and analyzing the results returned by the model's API.

## Features

- **Template-based Prompt Generation**: Easily create prompt templates and let PromptBlender fill in the parameters for you.
- **Automatic Parameter Combination**: Generates a Cartesian product of given parameters to explore a wide range of prompt possibilities.
- **API Integration**: Sends generated prompts to LLM APIs for execution (currently only ChatGPT).
- **Results Analysis and Consolidation**: Analyzes the responses from the LLMs, providing insights and consolidating the data for easy review.

## Getting Started

### Prerequisites

- Python 3.8 or later.
- Access to LLM APIs (currently only OpenAI's ChatGPT is supported).

### Installation

Clone the PromptBlender repository to your local machine:

```bash
pip install git+https://github.com/edanssandes/prompt-blender
```

### Graphical User Interface (GUI)

The PromptBlender project includes a user-friendly Graphical User Interface (GUI) that allows you to interact with the application easily. To open the GUI, you can run the following command in your terminal, without any parameter:

```
python -m prompt-blender [-h] [--job JOB] 
```

The GUI allows you to input prompts and parameters, blend the parameters in many prompt combinations, execute them using the LLM APIs, and export the responses to a zip file.


![Main Window](<docs/imgs/screenshot_main.png>)


### Command Line Interface (CLI)

```
usage: python -m prompt-blender [-h] [--job JOB] 
                 [--prompt-file PROMPT_FILE] 
                 [--args ARGS [ARGS ...]] 
                 [--output-dir OUTPUT_DIR] 
                 [--analysis-dir ANALYSIS_DIR] 
                 [--exec] 
                 [--recreate]
                 [--gpt-model GPT_MODEL] 
                 [--gpt-manual-ui] 
                 [--gpt-args GPT_ARGS [GPT_ARGS ...]] 
                 [--gpt-json]
                 [--analyse ANALYSE [ANALYSE ...]]

optional arguments:
  -h, --help            show this help message and exit
  --job JOB             Path to the job directory
  --prompt-file PROMPT_FILE
                        Path to the prompt file
  --args ARGS [ARGS ...]
                        List of file or directory arguments
  --output-dir OUTPUT_DIR
                        Path to the output directory
  --analysis-dir ANALYSIS_DIR
                        Path to the analysis directory
  --exec                Execute LLM with the generated prompts
  --recreate            Recreate the output files
  --gpt-model GPT_MODEL
                        Model name for chatgpt
  --gpt-args GPT_ARGS [GPT_ARGS ...]
                        List of arguments for chatgpt in the form key=value
  --gpt-json            Return the response in json format
  --gpt-manual-ui       Use manual UI for chatgpt. Same as --gpt-model=gpt-manual-ui
  --analyse ANALYSE [ANALYSE ...]
                        Python file used to analyse the output files. The file must 
                        contains a function called analyse(refs_values, content)
```

### Contributing
We welcome contributions to PromptBlender! If you have suggestions for improvements or 
new features, please open an issue or submit a pull request.

### License
PromptBlender is released under the MIT License. See the LICENSE file for more details.


