from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model import load_model

app = FastAPI(title="Invoice service")
model = load_model()


class InvoiceRequest(BaseModel):
    supplier: str
    total: float | None = None
    invoice_date: str | None = None


class InvoiceResponse(BaseModel):
    label: str
    score: float


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/score", response_model=InvoiceResponse)
def score(request: InvoiceRequest) -> InvoiceResponse:
    if not request.supplier.strip():
        raise HTTPException(status_code=422, detail="supplier is empty")
    label, probability = model.predict(request.model_dump())
    return InvoiceResponse(label=label, score=round(probability, 4))
