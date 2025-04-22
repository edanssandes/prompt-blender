import re
import json
import pandas as pd

analyse_info = {
    'name': 'GPT JSON',
    'description': 'Analyse the JSON responses from GPT models',
    'llm_modules': ['chatgpt', 'chatgpt_manual'],
}

def analyse(response):
    analysis = []

    for choice in response['choices']:
        content = choice['message']['content']

        try:
            # first try
            data = json.loads(content)
            analysis.append(data)
        except json.JSONDecodeError as e:
            # second try
            try:
                prefix, response, suffix = re.match(r"^(.*?```json\s*)([\{\[].{5,}[\}\]])(\s*```.*?)$", content, re.DOTALL).groups()
                data = json.loads(response)

                if isinstance(data, list):
                    data = {'response': data}  # Ensure it's a dict with a 'response' key pointing to the list

                analysis.append(data)
            except Exception as e:
                analysis.append({'_error': str(e)})

    return analysis
