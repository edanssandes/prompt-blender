from prompt_blender.llms.common.openai_compatible import OpenAICompatibleModule

module = OpenAICompatibleModule(
    ## General info
    id='7b633c8e-697d-4761-98f9-8bbc366ab755',
    name='Groq',
    description='Execute Groq models via API.',
    version='2.0.0',
    release_date='2026-03-06',
    cache_prefix='groq',

    ## API info
    base_url='https://api.groq.com/openai/v1',
    models=[
        "llama-3.3-70b-versatile", 
        "llama-3.1-8b-instant",
        "openai/gpt-oss-120b",
        "openai/gpt-oss-20b",
    ],
    default_model='llama-3.3-70b-versatile',
    environment_var='GROQ_API_KEY'
    )
