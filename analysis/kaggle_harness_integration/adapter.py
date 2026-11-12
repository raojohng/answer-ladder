"""Use ADK's official LiteLlm conversion with Kaggle's supplied model client.

ADK and swegemma own the agent/tool loop. This bridge only transports each
completion request and records its input/output. No tools execute in the SDK.
"""
import asyncio
import json
from pathlib import Path
import time

from google.adk.models.lite_llm import LiteLlm, LiteLLMClient
from litellm import ModelResponse


class KaggleCompletionClient(LiteLLMClient):
    def __init__(self, llm, record_path, record_sdk=True):
        self.llm = llm
        self.record_path = Path(record_path)
        self.record_sdk = record_sdk
        self.calls = 0

    async def acompletion(self, model, messages, tools=None, response_format=None, **kwargs):
        if kwargs.pop('stream', False):
            raise ValueError('The harness bridge currently supports non-streaming runs only.')
        # Preserve standard sampling parameters. Reject unsupported ones visibly.
        allowed = {'temperature', 'top_p', 'max_tokens', 'max_completion_tokens', 'stop',
                   'presence_penalty', 'frequency_penalty', 'seed', 'tool_choice',
                   'parallel_tool_calls', 'reasoning_effort', 'extra_body', 'timeout'}
        unknown = set(kwargs) - allowed
        if unknown:
            raise ValueError(f'Unmapped generation options: {sorted(unknown)}')
        # Kaggle's SDK never sends temperature through its model proxy (support_temperature=False, proxy bug
        # b/439876083 in kaggle_benchmarks/kaggle/model_proxy.py); mirror it and record what was dropped.
        dropped = {}
        if not getattr(self.llm, 'support_temperature', True) and 'temperature' in kwargs:
            dropped['temperature'] = kwargs.pop('temperature')
        request = dict(model=self.llm.model, messages=messages, **kwargs)
        if tools:
            request['tools'] = tools
        if response_format:
            request['response_format'] = response_format
        self.calls += 1
        started = time.monotonic()
        raw = await asyncio.to_thread(self.llm.client.chat.completions.create, **request)
        response = raw.model_dump(mode='json', exclude_none=True)
        row = dict(call=self.calls, request=request, response=response, dropped=dropped,
                   seconds=time.monotonic() - started)
        if self.record_sdk:
            # Recording into Kaggle's chat log is evidence, not part of the agent loop: a failure here must not end the run.
            try:
                import kaggle_benchmarks as kbench
                from kaggle_benchmarks.messages import Message
                from kaggle_benchmarks.actors import user
                usage = response.get('usage') or {}
                cost = usage.get('cost') or {}
                meta = dict(input_tokens=usage.get('prompt_tokens'), output_tokens=usage.get('completion_tokens'),
                            total_backend_latency_ms=usage.get('total_backend_latency_ms'), **cost)
                # Separate recorded conversations prevent duplicated cumulative history
                # from being mistaken for newly generated training turns.
                with kbench.chats.new(name=f'Official harness model call {self.calls}'):
                    user.send(json.dumps(request, default=str))
                    self.llm.send(Message(content=json.dumps(response['choices'][0]['message']),
                                          sender=self.llm, _meta=meta))
            except Exception as exc:
                row['sdk_record_error'] = f'{type(exc).__name__}: {exc}'
        self.record_path.parent.mkdir(parents=True, exist_ok=True)
        with self.record_path.open('a') as out:
            out.write(json.dumps(row, default=str) + '\n')
        return ModelResponse(**response)


def make_model(llm, record_path, record_sdk=True):
    if not hasattr(getattr(llm, 'client', None), 'chat'):
        raise TypeError('This adapter requires Kaggle\'s OpenAI-compatible model client.')
    client = KaggleCompletionClient(llm, record_path, record_sdk=record_sdk)
    model = LiteLlm(model='openai/' + llm.model, llm_client=client)
    return model, client
