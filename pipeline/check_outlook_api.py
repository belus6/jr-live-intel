"""Small request to diagnose runner-side API access without exposing credentials."""
import os
import sys
from generate_outlook import call_api, GenerationError, MODEL

try:
    key = os.environ.get('OPENAI_API_KEY')
    if not key: raise GenerationError('OPENAI_API_KEY is missing from repository Actions secrets.')
    print('Checking API access and research request parameters.', flush=True)
    result = call_api(key, {'model': MODEL, 'store': False, 'reasoning': {'effort': 'medium'},
        'max_output_tokens': 64, 'max_tool_calls': 1, 'tools': [{'type': 'web_search'}],
        'tool_choice': 'required', 'include': ['web_search_call.action.sources'],
        'input': 'Search the official United Nations website. Reply with only OK. This is a connectivity test.'})
    print('API accepted the configured model and web-search parameters. HTTP request succeeded.')
    print('Diagnostic response status: ' + ('completed' if result.get('status') == 'completed' else 'incomplete or other (expected with the small test token limit)'))
except GenerationError as error:
    sys.exit('API diagnostic failed: ' + str(error))
except (ValueError, TypeError, KeyError):
    sys.exit('API diagnostic returned an invalid response. Credentials and response bodies were not logged.')
