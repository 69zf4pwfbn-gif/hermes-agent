"""The optional Slack transport hook runs only after the normal channel gates."""

import ast
import asyncio
from pathlib import Path

import pytest


ADAPTER = Path(__file__).resolve().parents[2] / "plugins/platforms/slack/adapter.py"


def test_hook_is_after_authorization_and_before_model_dispatch():
    tree = ast.parse(ADAPTER.read_text(encoding="utf-8"))
    method = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "_handle_slack_message_impl"
    )
    source = ast.get_source_segment(ADAPTER.read_text(encoding="utf-8"), method)
    assert source.index("self._early_reject_unauthorized(") < source.index(
        "self._run_authorized_message_hook(")
    assert source.index("self._channel_gate_allows(") < source.index(
        "self._run_authorized_message_hook(")
    assert source.index("self._peer_bot_drop(") < source.index(
        "self._run_authorized_message_hook(")
    assert source.index("self._remember_processed_message_ts(_claim_ts)") < source.index(
        "self._run_authorized_message_hook(")
    assert source.index("self._run_authorized_message_hook(") < source.index(
        "await self.handle_message(msg_event)")


def test_hook_receives_original_transport_fields_and_can_decline():
    from plugins.platforms.slack.adapter import SlackAdapter

    adapter = object.__new__(SlackAdapter)
    adapter._authorized_message_hook = None
    seen = []

    async def hook(**kwargs):
        seen.append(kwargs)
        return False

    adapter.set_authorized_message_hook(hook)
    event = {"type": "message", "channel": "C123", "user": "U123"}
    body = {"type": "event_callback", "event": event, "event_id": "Ev123"}
    handled = asyncio.run(adapter._run_authorized_message_hook(
        event=event, body=body, team_id="T123", channel_id="C123",
        user_id="U123", text="start a new study buddy",
    ))
    assert handled is False
    assert seen == [{
        "event": event, "body": body, "team_id": "T123", "channel_id": "C123",
        "user_id": "U123", "text": "start a new study buddy",
    }]


def test_hook_failure_does_not_take_down_other_slack_messages():
    from plugins.platforms.slack.adapter import SlackAdapter

    adapter = object.__new__(SlackAdapter)

    async def failing_hook(**_kwargs):
        raise RuntimeError("plugin failure")

    adapter.set_authorized_message_hook(failing_hook)
    assert asyncio.run(adapter._run_authorized_message_hook(
        event={}, body={}, team_id="T", channel_id="C",
        user_id="U", text="hello",
    )) is False


@pytest.mark.parametrize("result", [True, False])
def test_hook_handled_result(result):
    from plugins.platforms.slack.adapter import SlackAdapter

    adapter = object.__new__(SlackAdapter)

    async def hook(**_kwargs):
        return result

    adapter.set_authorized_message_hook(hook)
    assert asyncio.run(adapter._run_authorized_message_hook(
        event={}, body={}, team_id="T", channel_id="C",
        user_id="U", text="hello",
    )) is result
