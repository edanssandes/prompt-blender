import re
import json
import pandas as pd
import dirtyjson

analyse_info = {
    'name': 'GPT JSON',
    'description': 'Analyse the JSON responses from GPT models',
    'llm_modules': ['chatgpt', 'chatgpt_manual'],
}



def analyse(response, timestamp):
    analysis = []

    if 'choices' in response:
        # Chat completions API (v1)
        outputs = response['choices']
        api_type = 'chat_completions_api'
    elif 'output' in response:
        # Response API (v2)
        outputs = response['output']
        api_type = 'response_api'
        #print(json.dumps(outputs, indent=2, ensure_ascii=False))
    elif not response:
        analysis.append({'_error': 'Null response', '_timestamp': timestamp})
        return analysis
    else:
        analysis.append({'_error': f'Unknown response format: {str(response.keys())}', '_timestamp': timestamp})
        return analysis
    
    if not outputs:
        analysis.append({'_error': 'Empty response from API', '_timestamp': timestamp})
        return analysis

    multiple_choices = len(outputs) > 1

    for idx_choice, choice in enumerate(outputs):
        #print(json.dumps(choice, indent=2, ensure_ascii=False))
        if api_type == 'chat_completions_api':
            content = choice['message']['content']
        elif api_type == 'response_api':
            if 'content' not in choice:
                continue
            content = choice['content'][0]['text']


        try:
            data = extract_json(content)

            if isinstance(data, list):
                data = {'response': data}  # Ensure it's a dict with a 'response' key pointing to the list

            if '_extra' in choice:
                extra = choice['_extra']
                data['_extra'] = extra

            data['_timestamp'] = timestamp

            if multiple_choices:
                if '_extra' not in data:
                    data['_extra'] = {}
                data['_extra']['_choice'] = idx_choice

            analysis.append(data)
        except ValueError as e:
            analysis.append({'_error': str(e), '_raw': content, '_timestamp': timestamp})


    return analysis

def extract_json(content):
    error = ""
    data = None

    if content is None:
        raise ValueError("Content is None")

    try:
            # first try
        if data is None:
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

    except Exception as e:
        error = error + str(e) + '\n'


    if data is None:
            # third try
        if content.startswith("'") and content.endswith("'"):
            data = {'text': content[1:-1]}

    try:
            # fourth try
        if data is None:
            prefix, response, suffix = re.match(r"^(.*?)([\{\[].{5,}[\}\]])(.*?)$", content, re.DOTALL).groups()
            data = json.loads(response)

    except Exception as e:
        error = error + str(e) + '\n'

    try:
            # fifth try
        if data is None:
            data = dirtyjson.loads(content)

    except Exception as e:
        error = error + str(e) + '\n'

    if data is None:
        if error:
            raise ValueError(f"Error parsing JSON: {error}")
        else:
            raise ValueError("JSON was parsed with no data")

    return data
