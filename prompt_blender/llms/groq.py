from prompt_blender.llms.common.openai_compatible import OpenAICompatibleModule

MODULE_UUID = '7b633c8e-697d-4761-98f9-8bbc366ab755'
VERSION = '1.0.0'
RELEASE_DATE = '2026-02-21'

module_info = {
    'id': MODULE_UUID,
    'name': 'Groq',
    'description': 'Execute Groq models via API.',
    'version': VERSION,
    'release_date': RELEASE_DATE,
    'cache_prefix': 'groq',
}


module = OpenAICompatibleModule(
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
