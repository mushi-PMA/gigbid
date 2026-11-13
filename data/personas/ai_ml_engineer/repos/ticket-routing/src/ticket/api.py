from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model import load_model

app = FastAPI(title="Ticket service")
model = load_model()


class TicketRequest(BaseModel):
    subject: str
    body_length: float | None = None
    channel: str | None = None


class TicketResponse(BaseModel):
    label: str
    score: float


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/score", response_model=TicketResponse)
def score(request: TicketRequest) -> TicketResponse:
    if not request.subject.strip():
        raise HTTPException(status_code=422, detail="subject is empty")
    label, probability = model.predict(request.model_dump())
    return TicketResponse(label=label, score=round(probability, 4))
