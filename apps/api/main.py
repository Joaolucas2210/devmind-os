from fastapi import FastAPI
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
    answer = await client.generate(
        f"Responda de forma objetiva em português:\n\n{request.question}"
    )
    return AskResponse(answer=answer)
