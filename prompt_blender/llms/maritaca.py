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
            'sabiazinho-4',
            'sabia-4-small',
            'sabiazim-4',
            'sabiá-3.1',
            'sabiá-3',
        ],
    default_model='sabia-4',
    environment_var='MARITACA_API_KEY'
    )
