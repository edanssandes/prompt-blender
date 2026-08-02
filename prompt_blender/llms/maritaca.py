from prompt_blender.llms.common.openai_compatible import OpenAICompatibleModule

module = OpenAICompatibleModule(
    ## General info
    id='d9198e4b-9913-4c75-9e9f-5372fc4660b5',
    name='Maritaca',
    description='Execute Maritaca models via API.',
    version='2.0.0',
    release_date='2026-03-06',
    cache_prefix='maritaca',

    ## API info
    base_url='https://chat.maritaca.ai/api',
    models=[
        'sabia-4',
        'sabia-4-br-sp',
        'sabia-4-thinking',
        'sabia-4-thinking-br-sp',
        'sabiazinho-4',
        'sabiazinho-4-br-sp',
    ],
    default_model='sabia-4',
    environment_var='MARITACA_API_KEY',
    costs={
        # Prices are BRL per 1M tokens (default mode).
        'sabia-4': {'input': 5.00, 'output': 20.00},
        'sabia-4-br-sp': {'input': 6.50, 'output': 26.00},
        'sabia-4-thinking': {'input': 5.00, 'output': 40.00},
        'sabia-4-thinking-br-sp': {'input': 6.50, 'output': 52.00},
        'sabiazinho-4': {'input': 1.00, 'output': 4.00},
        'sabiazinho-4-br-sp': {'input': 1.30, 'output': 5.20},
    }
)
