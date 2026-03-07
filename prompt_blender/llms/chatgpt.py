from prompt_blender.llms.common.openai_compatible import OpenAICompatibleModule

module = OpenAICompatibleModule(
    ## General info
    id='b85680ef-8da2-4ed5-b881-ce33fe5d3ec0',
    name='ChatGPT',
    description='Execute OpenAI models via API.',
    version='2.0.0',
    release_date='2026-03-06',
    cache_prefix='openai',

    ## API info
    base_url=None,  # Default
    models=[
        "gpt-4o-mini", 
        "gpt-4o", 
        "gpt-4-turbo", 
        "gpt-3.5-turbo", 
        "gpt-4o-mini-search-preview", 
        "gpt-4o-search-preview",
        "gpt-4.1-nano", 
        "gpt-4.1-mini", 
        "gpt-5-mini", 
        "gpt-5-nano",
        "gpt-5-search-api",            
    ],
    default_model='gpt-4.1-mini',
    environment_var='OPENAI_API_KEY'
    )
