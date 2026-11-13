from transformers import pipeline

_classifier = None


def get_classifier(model_name: str = "distilbert-base-uncased-finetuned-sst-2-english"):
    global _classifier
    if _classifier is None:
        _classifier = pipeline("text-classification", model=model_name, truncation=True, max_length=256)
    return _classifier


def score_batch(texts: list[str], batch_size: int = 16) -> list[dict]:
    results = get_classifier()(texts, batch_size=batch_size)
    return [{"transcript": text, "label": r["label"].lower(), "confidence": round(r["score"], 3)}
            for text, r in zip(texts, results)]
