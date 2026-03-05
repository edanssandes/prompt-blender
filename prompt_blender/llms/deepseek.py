from prompt_blender.llms.common.openai_compatible import OpenAICompatibleModule

MODULE_UUID = '475f4690-fb69-49ae-adb3-01d42e0677d5'
VERSION = '1.0.0'
RELEASE_DATE = '2026-02-21'

module_info = {
    'id': MODULE_UUID,
    'name': 'DeepSeek',
    'description': 'Execute DeepSeek models via API.',
    'version': VERSION,
    'release_date': RELEASE_DATE,
    'cache_prefix': 'deepseek',
}


module = OpenAICompatibleModule(
    base_url='https://api.deepseek.com',
    models=[
            "deepseek-chat",
            "deepseek-reasoning",
        ],
    default_model='deepseek-chat',
    environment_var='DEEPSEEK_API_KEY'
    )
