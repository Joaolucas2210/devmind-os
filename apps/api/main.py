from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from qdrant_client.http.exceptions import ResponseHandlingException, UnexpectedResponse

from apps.api.dependencies import (
    build_generator,
    build_retriever,
    get_generator,
    get_retriever,
)
from packages.application.answer_question import AnswerQuestion, Generator
from packages.application.retrieval import Retriever
from packages.shared.config import Settings, get_settings


class AskRequest(BaseModel):
    question: str


class SourceResponse(BaseModel):
    chunk_id: str
    file_path: str
    chunk_index: int
    score: float
    document_id: str | None = None


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceResponse] = Field(default_factory=list)


def create_app(
    *,
    settings: Settings | None = None,
    generator: Generator | None = None,
    retriever: Retriever | None = None,
) -> FastAPI:
    effective_settings = settings or get_settings()
    effective_generator = generator or build_generator(effective_settings)
    effective_retriever = retriever or build_retriever(effective_settings)
    app = FastAPI(title="DevMind OS API")
    app.state.settings = effective_settings
    app.state.generator = effective_generator
    app.state.retriever = effective_retriever

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ask", response_model=AskResponse)
    async def ask(
        request: AskRequest,
        generator: Annotated[Generator, Depends(get_generator)],
        retriever: Annotated[Retriever, Depends(get_retriever)],
    ) -> AskResponse:
        use_case = AnswerQuestion(generator, retriever)
        try:
            result = await use_case.execute(request.question)
        except (ResponseHandlingException, UnexpectedResponse) as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Qdrant indisponivel. Verifique QDRANT_URL e se o servico "
                    "esta ativo."
                ),
            ) from exc
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
        return AskResponse(
            answer=result.answer,
            sources=[SourceResponse(**source.__dict__) for source in result.sources],
        )

    return app


app = create_app()
