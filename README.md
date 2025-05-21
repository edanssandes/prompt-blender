# PromptBlender

## Overview

PromptBlender is a GUI tool designed to automate the generation, execution, and analysis of prompts for use with language learning models (LLMs). It simplifies the task of creating multiple prompts by automatically filling parameters within a template, generating a Cartesian product of prompts, and analyzing the results returned by the model's API.

## Features

- **Template-based Prompt Generation**: Easily create prompt templates and let PromptBlender automatically fill in the variables for you.
- **Automatic Parameter Combination**: Generates a cartesian product of given variables to explore a wide range of prompt possibilities.
- **Various data formats**: Supports many formats for loading variables data: spreedsheet (xlsx, xlsx, csv), json/jsonl, plain text, documents (pdf, docx). There is no OCR suport yet.
- **API Integration**: Sends generated prompts to LLM APIs for execution (currently OpenAI/ChatGPT and Groq Cloud models).
- **Plugins**: Support customized plugin for integration with other APIs, LLM aplications or web Interfaces.
- **Results Analysis and Consolidation**: Analyzes responses from LLMs, providing insights and consolidating the data in spreedsheet for easy review.
- **Budget limit**: Allows setting a budget limit to prevent excessive usage.
- **Exporting results**: Saves execution results for historical tracking logs or for sharing purposes.


## Getting Started

### Prerequisites

- Python 3.11 or later.
- Access to LLM APIs (currently only OpenAI's ChatGPT and Groq Cloud is supported).

### Anaconda Environment (optional)

Before installation, you may want to create an Anaconda environment to manage dependencies and isolate your project, ensuring that the installation and running of your project doesn't affect or interfere with other Python projects. You can create the environment by running the following command in your terminal:

```bash
conda create -n prompt-blender python=3.11
```

In order to activate the environment, run:

```bash
conda activate prompt-blender
```


### Installation

Install some dependencies (workaround for the large dependency list of browser-use agent).
```bash
conda install wxpython  
pip install browser-use --no-deps
pip install langchain_community --no-deps
```


Install the PromptBlender repository to your local machine:

```bash
pip install git+https://github.com/edanssandes/prompt-blender
```

### Graphical User Interface (GUI)

The PromptBlender project includes a user-friendly Graphical User Interface (GUI) that allows you to interact with the application easily. To open the GUI, you can run the following command in your terminal, without any parameter:

```
python -m prompt-blender
```

The GUI allows you to input prompts and parameters, blend the parameters in many prompt combinations, execute them using the LLM APIs, and export the responses to a zip file.


![Main Window](<docs/imgs/screenshot_main.png>)


![Execution configuration](<docs/imgs/screenshot_execution.png>)

### Contributing
We welcome contributions to PromptBlender! If you have suggestions for improvements or 
new features, please open an issue or submit a pull request.

### License
PromptBlender is released under the MIT License. See the LICENSE file for more details.


