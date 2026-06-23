from prompt_blender.llms.common.openai_compatible import OpenAICompatibleModule

module = OpenAICompatibleModule(
    ## General info
    id='475f4690-fb69-49ae-adb3-01d42e0677d5',
    name='DeepSeek',
    description='Execute DeepSeek models via API.',
    version='2.0.0',
    release_date='2026-03-06',
    cache_prefix='deepseek',

    ## API info
    base_url='https://api.deepseek.com',
    models=[
            "deepseek-chat",
            "deepseek-reasoning",
        ],
    default_model='deepseek-chat',
    environment_var='DEEPSEEK_API_KEY'
    )
