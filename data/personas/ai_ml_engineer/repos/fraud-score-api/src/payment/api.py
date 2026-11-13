from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model import load_model

app = FastAPI(title="Payment service")
model = load_model()


class PaymentRequest(BaseModel):
    merchant: str
    amount: float | None = None
    country: str | None = None


class PaymentResponse(BaseModel):
    label: str
    score: float


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/score", response_model=PaymentResponse)
def score(request: PaymentRequest) -> PaymentResponse:
    if not request.merchant.strip():
        raise HTTPException(status_code=422, detail="merchant is empty")
    label, probability = model.predict(request.model_dump())
    return PaymentResponse(label=label, score=round(probability, 4))
