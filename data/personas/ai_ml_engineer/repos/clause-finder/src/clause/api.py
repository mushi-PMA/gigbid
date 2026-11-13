from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model import load_model

app = FastAPI(title="Clause service")
model = load_model()


class ClauseRequest(BaseModel):
    question: str
    score: float | None = None
    contract_id: str | None = None


class ClauseResponse(BaseModel):
    label: str
    score: float


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/score", response_model=ClauseResponse)
def score(request: ClauseRequest) -> ClauseResponse:
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="question is empty")
    label, probability = model.predict(request.model_dump())
    return ClauseResponse(label=label, score=round(probability, 4))
