analyse_info = {
    'name': 'Cost',
    'description': 'Summarize total token usage and total cost',
}

def analyse(response, usage=None, **kwargs):
    usage = usage or {}
    return {
        'tokens in': usage.get('tokens in', response.get('tokens in', 0)),
        'tokens out': usage.get('tokens out', response.get('tokens out', 0)),
        'bytes in': usage.get('bytes in', response.get('bytes in', 0)),
        'bytes out': usage.get('bytes out', response.get('bytes out', 0)),
        'cost in': usage.get('cost in', response.get('cost in', 0.0)),
        'cost out': usage.get('cost out', response.get('cost out', 0.0)),
    }


def reduce(results):
    total_tokens_input = 0
    total_tokens_output = 0
    total_bytes_input = 0
    total_bytes_output = 0
    total_cost_input = 0.0
    total_cost_output = 0.0

    for result in results:
        total_tokens_input += result.get('tokens in', 0)
        total_tokens_output += result.get('tokens out', 0)
        total_bytes_input += result.get('bytes in', 0)
        total_bytes_output += result.get('bytes out', 0)
        total_cost_input += result.get('cost in', 0.0)
        total_cost_output += result.get('cost out', 0.0)

    print('-' * 60)
    print('Tokens input:', total_tokens_input)
    print('Tokens output:', total_tokens_output)
    print('Bytes input:', total_bytes_input)
    print('Bytes output:', total_bytes_output)
    print('Cost input: US$', total_cost_input)
    print('Cost output: US$', total_cost_output)
    print('Total cost: US$', total_cost_input + total_cost_output)
    print('-' * 60)

    return {
        'Tokens Input': total_tokens_input,
        'Tokens Output': total_tokens_output,
        'Bytes Input': total_bytes_input,
        'Bytes Output': total_bytes_output,
        'Cost Input': total_cost_input,
        'Cost Output': total_cost_output,
        'Cost': total_cost_input + total_cost_output,
    }
