from prompt_blender.llms.common.openai_compatible import OpenAICompatibleModule

MODULE_UUID = 'd9198e4b-9913-4c75-9e9f-5372fc4660b5'
VERSION = '1.0.0'
RELEASE_DATE = '2026-02-21'

module_info = {
    'id': MODULE_UUID,
    'name': 'Maritaca',
    'description': 'Execute Maritaca models via API.',
    'version': VERSION,
    'release_date': RELEASE_DATE,
    'cache_prefix': 'maritaca',
}


module = OpenAICompatibleModule(
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
