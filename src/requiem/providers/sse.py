import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from requiem.providers.models import FinishReason, StreamEvent, TokenUsage, ToolCallRequest


def _parse_tool_args(args_str: str) -> dict[str, object]:
    if not args_str:
        return {}
    try:
        parsed = json.loads(args_str)
    except json.JSONDecodeError:
        return {"raw": args_str}
    return parsed if isinstance(parsed, dict) else {"raw": parsed}


async def parse_sse_stream(
    resp: httpx.Response,
    *,
    model: str = '',
    provider: str = 'openai',
    request_id: str = '',
) -> AsyncIterator[StreamEvent]:
    '''Parse an OpenAI Chat Completions SSE stream, yielding StreamEvents.'''
    colon = chr(58)
    done = chr(91) + chr(68) + chr(79) + chr(78) + chr(69) + chr(93)

    tool_acc: dict[int, dict[str, str]] = {}
    usage_data: dict[str, Any] | None = None
    final_finish: str | None = None

    async for raw_line in resp.aiter_lines():
        line = raw_line.strip()
        if not line or line.startswith(colon):
            continue
        if not line.startswith('data:'):
            continue
        payload = line[5:].strip()
        if not payload:
            continue
        if payload == done:
            break
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if data.get('error'):
            yield StreamEvent(type='error', error=str(data.get('error')))
            return
        if data.get('usage'):
            usage_data = data['usage']
        for choice in data.get('choices') or []:
            delta = choice.get('delta') or {}
            if choice.get('finish_reason'):
                final_finish = choice['finish_reason']
            content = delta.get('content')
            if content:
                yield StreamEvent(type='content_delta', content=content)
            for tc in delta.get('tool_calls') or []:
                idx = tc.get('index') or 0
                fn = tc.get('function') or {}
                args_fragment = fn.get('arguments') or ''
                acc = tool_acc.setdefault(idx, {"id": "", "name": "", "args": ""})
                tc_id = tc.get('id')
                if tc_id:
                    acc['id'] = tc_id
                name = fn.get('name')
                if name:
                    acc['name'] = name
                if args_fragment:
                    acc['args'] += args_fragment
        for idx, acc in tool_acc.items():
            if acc['args']:
                yield StreamEvent(
                    type='tool_call_delta',
                    tool_call_index=idx,
                    tool_call=ToolCallRequest(
                        id=acc['id'],
                        name=acc['name'],
                        arguments=_parse_tool_args(acc['args']),
                    ),
                )
    if usage_data:
        yield StreamEvent(
            type='usage',
            usage=TokenUsage(
                input_tokens=int(usage_data.get('prompt_tokens', 0)),
                output_tokens=int(usage_data.get('completion_tokens', 0)),
                total_tokens=int(usage_data.get('total_tokens', 0)),
                cached_tokens=int((usage_data.get('prompt_tokens_details') or {}).get('cached_tokens', 0)),
                provider=provider,
                model=model,
            ),
        )
    yield StreamEvent(type='finish', finish_reason=FinishReason.from_provider(final_finish))
