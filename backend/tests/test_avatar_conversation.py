import json

import pytest
from fastapi.testclient import TestClient

from nunti.avatar_studio.api import Settings, create_app
from nunti.avatar_studio.conversation import (
    DEFAULT_MODEL,
    ConversationInput,
    ConversationReply,
    build_request,
    read_reply,
)
from nunti.avatar_studio.storage import StudioError

TOKEN = "test-conversation-token-0123456789012345"
PATH = "/v3/conversation"
ORIGIN = "http://127.0.0.1:8768"


def test_request_uses_verified_trip_summary_and_recent_turns():
    value = ConversationInput(
        message="방금 정한 이름을 소개 문장에 써 줘.",
        history=[{"role": "assistant", "content": "달빛잔이라고 불러볼까?"}],
        trip={"destination": "버드나무 공방", "routeKm": 15.6, "routeMinutes": 20},
    )
    payload = build_request(DEFAULT_MODEL, value)
    assert payload["store"] is False
    assert payload["text"]["format"]["strict"] is True
    assert "tools" not in payload
    assert payload["input"][0]["content"] == "달빛잔이라고 불러볼까?"
    context = json.loads(payload["input"][1]["content"])
    assert context["trip"]["routeMinutes"] == 20
    assert context["message"] == value.message


@pytest.mark.parametrize(
    "part,code",
    [
        ({"type": "refusal", "refusal": "refused"}, "CONVERSATION_REFUSED"),
        (
            {"type": "output_text", "text": '{"reply":"안녕","gesture":"arbitrary-command"}'},
            "CONVERSATION_INVALID_RESPONSE",
        ),
    ],
)
def test_refusal_and_unrecognized_gesture_are_not_rendered(part, code):
    with pytest.raises(StudioError, match=code):
        read_reply(
            {
                "status": "completed",
                "output": [{"type": "message", "role": "assistant", "content": [part]}],
            }
        )


def test_endpoint_authentication_and_route_coordinates_are_rejected(tmp_path):
    calls = []

    def generate(key, model, value):
        calls.append(value.message)
        return ConversationReply(reply="작은 접시에 달빛을 담아 보자.", gesture="smile")

    settings = Settings(TOKEN, tmp_path, chat_enabled=True, chat_key="fixture-key")
    with TestClient(
        create_app(settings, conversation_generator=generate),
        base_url=ORIGIN,
        client=("127.0.0.1", 52100),
    ) as client:
        headers = {"Authorization": "Bearer " + TOKEN}
        message = {"message": "달빛이 담긴 접시를 빚을 거야."}
        assert client.post(PATH, json=message).status_code == 401
        assert (
            client.post(
                PATH, json={**message, "trip": {"latitude": 37.4}}, headers=headers
            ).status_code
            == 422
        )
        assert calls == []
        response = client.post(PATH, json=message, headers=headers)
        assert response.json()["data"]["gesture"] == "smile"
        assert calls == [message["message"]]


def test_missing_configuration_never_calls_provider(tmp_path):
    def generate(*args):
        pytest.fail("Disabled cloud conversation called its provider")

    with TestClient(
        create_app(Settings(TOKEN, tmp_path), conversation_generator=generate),
        base_url=ORIGIN,
        client=("127.0.0.1", 52100),
    ) as client:
        response = client.post(
            PATH, json={"message": "안녕"}, headers={"Authorization": "Bearer " + TOKEN}
        )
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "CONVERSATION_NOT_CONFIGURED"
