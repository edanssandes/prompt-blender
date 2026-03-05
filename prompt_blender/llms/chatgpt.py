from prompt_blender.llms.common.openai_compatible import OpenAICompatibleModule

MODULE_UUID = 'b85680ef-8da2-4ed5-b881-ce33fe5d3ec0'
VERSION = '1.0.0'
RELEASE_DATE = '2025-07-01'

module_info = {
    'id': MODULE_UUID,
    'name': 'ChatGPT',
    'description': 'Execute OpenAI models via API.',
    'version': VERSION,
    'release_date': RELEASE_DATE,
    'cache_prefix': 'openai',
}

module = OpenAICompatibleModule(
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
