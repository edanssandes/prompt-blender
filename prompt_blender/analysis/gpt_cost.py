import json

analyse_info = {
    'name': 'GPT Cost',
    'description': 'Analyse the cost of GPT responses',
    'llm_modules': ['chatgpt', 'chatgpt_manual'],
}

def analyse(response):
    usage = response.get("usage", None)
    if usage is None:
        return None

    tokens_in = usage['prompt_tokens']
    tokens_out = usage['completion_tokens']

    # FIXME duplicated code
    if response['model'] == 'gpt-3.5-turbo-0125':
        cost_in = 0.50
        cost_out = 1.50
    elif response['model'] == 'gpt-4-0125-preview':
        cost_in = 10.00
        cost_out = 30.00
    elif response['model'] == 'gpt-4o-2024-05-13':
        cost_in = 5.00
        cost_out = 15.00
    elif response['model'] == 'gpt-4o-2024-08-06':
        cost_in = 2.50
        cost_out = 10.00        
    elif response['model'] == 'gpt-manual-ui':
        cost_in = 0.00
        cost_out = 0.00
    elif response['model'] == 'gpt-4o-mini-2024-07-18':
        cost_in = 0.15
        cost_out = 0.60
        
    total_cost_in = tokens_in/1000000*cost_in
    total_cost_out = tokens_out/1000000*cost_out

    return {
        'tokens in': tokens_in,
        'tokens out': tokens_out,
        'cost in': total_cost_in,
        'cost out': total_cost_out,
    }

def reduce(results):
    total_tokens_in = 0
    total_tokens_out = 0
    total_cost = 0
    for result in results:
        total_tokens_in += result['tokens in']
        total_tokens_out += result['tokens out']
        total_cost += result['cost in'] + result['cost out']

    print('-'*60)
    print('Tokens in:', total_tokens_in)
    print('Tokens out:', total_tokens_out)
    print('Total cost: US$', total_cost)
    print('-'*60)

    return {
        'total tokens in': total_tokens_in,
        'total tokens out': total_tokens_out,
        'total cost': total_cost
    }
