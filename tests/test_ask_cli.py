from __future__ import annotations

import httpx
import pytest

from apps.api.ask import ask_api, main


def test_ask_api_posts_question_and_returns_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "http://api.test/ask"
        assert request.read() == b'{"question":"qual e o status?"}'
        return httpx.Response(200, json={"answer": "ok"})

    transport = httpx.MockTransport(handler)

    answer = ask_api(
        "qual e o status?",
        base_url="http://api.test/",
        transport=transport,
    )

    assert answer == "ok"


def test_ask_api_rejects_invalid_response() -> None:
    transport = httpx.MockTransport(
        lambda _request: httpx.Response(200, json={"message": "ok"})
    )

    with pytest.raises(RuntimeError, match="answer"):
        ask_api("pergunta", base_url="http://api.test", transport=transport)


def test_main_requires_question(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "Informe uma pergunta" in captured.err
