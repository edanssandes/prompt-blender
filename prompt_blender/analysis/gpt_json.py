import re
import json
import pandas as pd
import dirtyjson

analyse_info = {
    'name': 'GPT JSON',
    'description': 'Analyse the JSON responses from GPT models',
    'llm_modules': ['chatgpt', 'chatgpt_manual'],
}

def analyse(response):
    analysis = []

    for choice in response['choices']:
        content = choice['message']['content']

        data = None
        error = ""
        try:
            # first try
            data = json.loads(content)

            if isinstance(data, str):
                data = {'text': data}  # Ensure it's a dict with a 'text' key pointing to the string

        except json.JSONDecodeError as e:
            error = error + str(e) + '\n'

        try:
            # second try
            if data is None:
                prefix, response, suffix = re.match(r"^(.*?```json\s*)([\{\[].{5,}[\}\]])(\s*```.*?)$", content, re.DOTALL).groups()
                data = json.loads(response)

                if isinstance(data, list):
                    data = {'response': data}  # Ensure it's a dict with a 'response' key pointing to the list
        except Exception as e:
            error = error + str(e) + '\n'


        if data is None:
            # third try
            if content.startswith("'") and content.endswith("'"):
                data = {'text': content[1:-1]}


        try:
            # second try
            if data is None:
                prefix, response, suffix = re.match(r"^(.*?)([\{\[].{5,}[\}\]])(.*?)$", content, re.DOTALL).groups()
                data = json.loads(response)

                if isinstance(data, list):
                    data = {'response': data}  # Ensure it's a dict with a 'response' key pointing to the list
        except Exception as e:
            error = error + str(e) + '\n'

        try:
            # fourth try
            if data is None:
                data = dirtyjson.loads(content)
        except Exception as e:
            error = error + str(e) + '\n'

        if data is not None:
            if '_extra' in choice:
                extra = choice['_extra']
                data['_extra'] = extra
            analysis.append(data)
        else:
            analysis.append({'_error': error, '_raw': content})


    return analysis
