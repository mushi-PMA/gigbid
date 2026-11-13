from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model import load_model

app = FastAPI(title="Call service")
model = load_model()


class CallRequest(BaseModel):
    transcript: str
    duration: float | None = None
    queue: str | None = None


class CallResponse(BaseModel):
    label: str
    score: float


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/score", response_model=CallResponse)
def score(request: CallRequest) -> CallResponse:
    if not request.transcript.strip():
        raise HTTPException(status_code=422, detail="transcript is empty")
    label, probability = model.predict(request.model_dump())
    return CallResponse(label=label, score=round(probability, 4))
