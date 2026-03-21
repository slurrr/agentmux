from agentmux.codex_responses_proxy import normalize_responses_payload


def test_normalize_responses_payload_upgrades_assistant_message_items() -> None:
    payload = {
        'model': 'Qwen3.5-9B',
        'input': [
            {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'hi'}]},
            {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'hello'}]},
        ],
    }

    normalized = normalize_responses_payload(payload)
    assistant = normalized['input'][1]
    assert assistant['role'] == 'assistant'
    assert assistant['type'] == 'message'
    assert assistant['status'] == 'completed'
    assert assistant['id'].startswith('msg_proxy_1_')
    assert assistant['content'][0]['type'] == 'output_text'
    assert assistant['content'][0]['annotations'] == []
    assert assistant['content'][0]['logprobs'] == []


def test_normalize_responses_payload_leaves_other_items_alone() -> None:
    payload = {
        'input': [
            {'type': 'message', 'role': 'developer', 'content': [{'type': 'input_text', 'text': 'rules'}]},
            {'type': 'reasoning', 'id': 'rs_1', 'summary': [], 'type': 'reasoning'},
        ]
    }
    normalized = normalize_responses_payload(payload)
    assert normalized == payload
