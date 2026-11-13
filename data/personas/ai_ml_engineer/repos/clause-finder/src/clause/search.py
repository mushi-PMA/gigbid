import numpy as np
from openai import OpenAI

client = OpenAI()
EMBED_MODEL = "text-embedding-3-small"


def chunk(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    pieces, start = [], 0
    while start < len(text):
        pieces.append(text[start:start + size])
        start += size - overlap
    return pieces


def embed(texts: list[str]) -> np.ndarray:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    vectors = np.array([item.embedding for item in response.data], dtype="float32")
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


class Index:
    def __init__(self, documents: list[str]):
        self.chunks = [piece for doc in documents for piece in chunk(doc)]
        self.vectors = embed(self.chunks)

    def search(self, question: str, k: int = 5) -> list[tuple[float, str]]:
        scores = self.vectors @ embed([question])[0]
        best = np.argsort(-scores)[:k]
        return [(float(scores[i]), self.chunks[i]) for i in best]


def answer(index: Index, question: str) -> str:
    context = "\n---\n".join(text for _, text in index.search(question))
    reply = client.chat.completions.create(
        model="gpt-4o-mini", temperature=0,
        messages=[{"role": "system", "content": "Answer only from the context. Quote the clause."},
                  {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}])
    return reply.choices[0].message.content
