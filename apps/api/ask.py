from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from packages.shared.config import get_settings  # noqa: E402

DEFAULT_API_BASE_URL = "http://localhost:8000"


def _question_from_args(args: Sequence[str]) -> str:
    question = " ".join(args).strip()
    if not question:
        raise ValueError('Informe uma pergunta. Exemplo: make ask q="qual e o status?"')
    return question


def ask_api(
    question: str,
    *,
    base_url: str | None = None,
    timeout: float = 30,
    transport: httpx.BaseTransport | None = None,
) -> str:
    configured_base_url = base_url or str(get_settings().api_base_url)
    api_base_url = (configured_base_url or DEFAULT_API_BASE_URL).rstrip("/")

    with httpx.Client(timeout=timeout, transport=transport) as client:
        response = client.post(f"{api_base_url}/ask", json={"question": question})
        response.raise_for_status()

    data: Any = response.json()
    if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
        raise RuntimeError("Resposta invalida da API: campo 'answer' ausente.")

    return data["answer"]


def main(argv: Sequence[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else list(argv)
    base_url = DEFAULT_API_BASE_URL

    try:
        question = _question_from_args(args)
        base_url = str(get_settings().api_base_url).rstrip("/")
        answer = ask_api(question, base_url=base_url)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except httpx.ConnectError:
        print(
            f"Nao foi possivel conectar na API em {base_url}. "
            "Inicie a API com `make api`.",
            file=sys.stderr,
        )
        return 1
    except httpx.HTTPStatusError as exc:
        print(
            f"API retornou HTTP {exc.response.status_code}: {exc.response.text}",
            file=sys.stderr,
        )
        return 1
    except (httpx.TimeoutException, httpx.RequestError) as exc:
        print(f"Erro ao enviar pergunta para API: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
