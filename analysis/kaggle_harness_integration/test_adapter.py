"""Exercise ADK conversion across a tool call and its matching tool result."""
import asyncio
import json
from types import SimpleNamespace

from google.adk.models.llm_request import LlmRequest
from google.genai import types
from openai.types.chat import ChatCompletion
import pytest

from adapter import make_model


def test_official_adk_tool_roundtrip(tmp_path):
    requests = []

    def create(**request):
        requests.append(request)
        message = ({'role': 'assistant', 'tool_calls': [{
            'id': 'call_probe_123', 'type': 'function',
            'function': {'name': 'run_command', 'arguments': '{"command":"git diff"}'}}]}
            if len(requests) == 1 else {'role': 'assistant', 'content': 'Verified.'})
        return ChatCompletion.model_validate({
            'id': f'probe-{len(requests)}', 'object': 'chat.completion', 'created': 0,
            'model': 'probe-model', 'choices': [{'index': 0, 'message': message,
                'finish_reason': 'tool_calls' if len(requests) == 1 else 'stop'}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}})

    llm = SimpleNamespace(model='probe-model', client=SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
    model, bridge = make_model(llm, tmp_path/'calls.jsonl', record_sdk=False)
    request = LlmRequest(contents=[types.Content(role='user', parts=[types.Part(text='Inspect.')])],
        config=types.GenerateContentConfig(temperature=0, max_output_tokens=2048,
            system_instruction='Use the supplied tools.', tools=[types.Tool(function_declarations=[
                types.FunctionDeclaration(name='run_command', parameters_json_schema={
                    'type': 'object', 'properties': {'command': {'type': 'string'}},
                    'required': ['command']})])]))

    async def run():
        first = [r async for r in model.generate_content_async(request)]
        call = first[0].content.parts[0].function_call
        assert call.id == 'call_probe_123'
        assert call.name == 'run_command'
        assert call.args == {'command': 'git diff'}
        request.contents.extend([first[0].content, types.Content(role='user', parts=[
            types.Part(function_response=types.FunctionResponse(
                id=call.id, name=call.name, response={'output': 'diff result'}))])])
        second = [r async for r in model.generate_content_async(request)]
        assert second[0].content.parts[0].text == 'Verified.'
        assert second[0].usage_metadata.total_token_count == 15
        with pytest.raises(ValueError, match='Unmapped generation'):
            await bridge.acompletion('ignored', [], top_k=40)
        with pytest.raises(ValueError, match='non-streaming'):
            await bridge.acompletion('ignored', [], stream=True)

    asyncio.run(run())
    assert bridge.calls == 2
    assert requests[0]['model'] == 'probe-model'
    assert requests[0]['max_completion_tokens'] == 2048
    assert requests[0]['tools'][0]['function']['name'] == 'run_command'
    tool_result = next(m for m in requests[1]['messages'] if m['role'] == 'tool')
    assert tool_result['tool_call_id'] == 'call_probe_123'
    assert 'diff result' in tool_result['content']
    records = [json.loads(s) for s in (tmp_path/'calls.jsonl').read_text().splitlines()]
    assert len(records) == 2
    assert records[1]['response']['usage']['total_tokens'] == 15
