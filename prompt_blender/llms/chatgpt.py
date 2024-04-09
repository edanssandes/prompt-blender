from openai import OpenAI

client = None

def exec_init():
    global client
    client = OpenAI()


def exec(prompt, gpt_model, gpt_args, gpt_json=False):
    messages = []
    messages.append({"role": "user", "content": prompt})

    if gpt_json:
        gpt_args['response_format'] = { "type": "json_object" }

    response = client.chat.completions.create(
        model=gpt_model,
        messages=messages,
        **gpt_args
    )

    return response.model_dump()

def exec_close():
    global client
    client = None

        
