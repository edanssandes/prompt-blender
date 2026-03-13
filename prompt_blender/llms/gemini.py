from prompt_blender.llms.common.openai_compatible import OpenAICompatibleModule

module = OpenAICompatibleModule(
    ## General info
    id='34e003ba-b9a6-4dec-a92f-7c6f0a4f12bc',
    name='Gemini',
    description='Execute Google Gemini models via API.',
    version='2.0.0',
    release_date='2026-03-13',
    cache_prefix='gemini',

    ## API info
    base_url='https://generativelanguage.googleapis.com/v1beta/openai/',
    models=[
        "gemini-3.1-pro-preview",
        "gemini-3.1-pro-preview-customtools",
        "gemini-3.1-flash-lite-preview",
        "gemini-3-flash-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",

    ],
    default_model='gemini-3.1-flash-lite-preview',
    environment_var='GEMINI_API_KEY'
    )
