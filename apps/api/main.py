from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from apps.api.dependencies import build_generator, get_generator
from packages.application.answer_question import AnswerQuestion, Generator
from packages.shared.config import Settings, get_settings


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


def create_app(
    *,
    settings: Settings | None = None,
    generator: Generator | None = None,
) -> FastAPI:
    effective_settings = settings or get_settings()
    effective_generator = generator or build_generator(effective_settings)
    app = FastAPI(title="DevMind OS API")
    app.state.settings = effective_settings
    app.state.generator = effective_generator

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ask", response_model=AskResponse)
    async def ask(
        request: AskRequest,
        generator: Annotated[Generator, Depends(get_generator)],
    ) -> AskResponse:
        use_case = AnswerQuestion(generator)
        try:
            answer = await use_case.execute(request.question)
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Ollama indisponivel. Verifique OLLAMA_BASE_URL e se o servico "
                    "esta ativo."
                ),
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=502,
                detail=(
                    f"Ollama retornou HTTP {exc.response.status_code}. "
                    "Verifique OLLAMA_CHAT_MODEL e os modelos instalados."
                ),
            ) from exc
        return AskResponse(answer=answer)

    return app


app = create_app()
