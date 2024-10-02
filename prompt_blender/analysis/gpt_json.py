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
            data = json.loads(content)
            analysis.append(data)
        except json.JSONDecodeError as e:
            analysis.append({'_error': str(e)})

    return analysis
