import json
import os
from pathlib import Path
import httpx
from tools.copy_policy import violations
from tools.mock_providers import MockLanguageProvider
from tools.catalog import CITIES

class GroqLanguageProvider:
    def call(self, name, data):
        prompt = (Path(__file__).resolve().parents[1] / 'prompts' / f'{name}.txt').read_text()
        response = httpx.post('https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f"Bearer {os.environ['GROQ_API_KEY']}"},
            json={'model': os.getenv('GROQ_MODEL', 'llama-3.3-70b-versatile'),
                  'temperature': 0, 'max_tokens': 600, 'response_format': {'type': 'json_object'},
                  'messages': [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': json.dumps(data)}]}, timeout=30)
        response.raise_for_status()
        return json.loads(response.json()['choices'][0]['message']['content'])
    def order(self, trip, count):
        order = self.call('itinerary', {'trip': trip, 'clusters': CITIES[trip['destination']]['clusters'], 'indexes': list(range(count))}).get('order')
        if not isinstance(order, list) or any(type(i) is not int for i in order) or sorted(order) != list(range(count)):
            raise ValueError('Invalid itinerary response.')
        return order
    def report(self, state):
        value = self.call('report', {'trip': state['trip'], 'changes': state['changes']}).get('summary')
        if not isinstance(value, str) or not value.strip() or len(value) > 1200 or violations(value):
            raise ValueError('Report failed copy validation.')
        return value

class OpenAILanguageProvider(GroqLanguageProvider):
    """OpenAI Responses API with strict JSON schemas and server-only credentials."""
    def call(self, name, data):
        prompt = (Path(__file__).resolve().parents[1] / 'prompts' / f'{name}.txt').read_text()
        field = 'order' if name == 'itinerary' else 'summary'
        field_schema = {'type': 'array', 'items': {'type': 'integer'}} if field == 'order' else {'type': 'string'}
        headers = {'Authorization': f"Bearer {os.environ['OPENAI_API_KEY']}"}
        if os.getenv('OPENAI_PROJECT_ID'):
            headers['OpenAI-Project'] = os.environ['OPENAI_PROJECT_ID']
        response = httpx.post('https://api.openai.com/v1/responses', headers=headers,
            json={'model': os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'), 'store': False,
                  'max_output_tokens': 800, 'instructions': prompt, 'input': json.dumps(data),
                  'text': {'format': {'type': 'json_schema', 'name': f'travel_{name}', 'strict': True,
                      'schema': {'type': 'object', 'properties': {field: field_schema},
                                 'required': [field], 'additionalProperties': False}}}}, timeout=30)
        response.raise_for_status()
        payload = response.json()
        if payload.get('status') != 'completed':
            raise ValueError('OpenAI did not complete the planning response.')
        parts = [content['text'] for item in payload.get('output', []) if item.get('type') == 'message'
                 for content in item.get('content', []) if content.get('type') == 'output_text']
        if not parts:
            raise ValueError('OpenAI returned no planning content.')
        result = json.loads(''.join(parts))
        if not isinstance(result, dict):
            raise ValueError('Invalid OpenAI planning response.')
        return result


def is_live():
    return os.getenv('LLM_PROVIDER', 'mock') in ('live', 'groq', 'openai')


def provider():
    mode = os.getenv('LLM_PROVIDER', 'mock')
    if mode == 'openai':
        return OpenAILanguageProvider()
    if mode in ('live', 'groq'):
        return GroqLanguageProvider()
    return MockLanguageProvider()
