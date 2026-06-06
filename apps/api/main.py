import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from packages.shared.ollama_client import OllamaClient

app = FastAPI(title="DevMind OS API")


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest) -> AskResponse:
    client = OllamaClient()
    try:
        answer = await client.generate(
            f"Responda de forma objetiva em português:\n\n{request.question}"
        )
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
