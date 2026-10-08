from __future__ import annotations
import hashlib, json, logging, math, os
from dataclasses import dataclass
from typing import Any

log = logging.getLogger("chilli.rag")

@dataclass
class VectorDocument:
    id: str
    text: str
    metadata: dict
    vector: list[float]

def _local_embedding(text: str, dimensions: int = 3072) -> list[float]:
    vector = [0.0] * dimensions
    for token in text.lower().split():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        vector[int.from_bytes(digest[:4], "big") % dimensions] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(v*v for v in vector)) or 1.0
    return [v/norm for v in vector]

def protect_workbook_text(value: Any) -> str:
    text = str(value or "")
    # Workbook cells are data, never instructions. Keep suspicious content
    # visible for audit while neutralising common instruction delimiters.
    for marker in ("ignore previous", "system:", "assistant:", "developer:", "<|", "jailbreak"):
        text = text.replace(marker, "[blocked workbook text]")
        text = text.replace(marker.title(), "[blocked workbook text]")
    return text

class EvidenceIndex:
    def __init__(self):
        self.documents: list[VectorDocument] = []
        self.provider, self.model = "local-fallback", "local-hash-256"
        self.last_error = None

    def build(self, records):
        vectors = self._embed([r["text"] for r in records])
        self.documents = [VectorDocument(r["id"], r["text"], r["metadata"], v) for r, v in zip(records, vectors)]
        return len(self.documents)

    def _embed(self, texts):
        if os.getenv("OPENAI_API_KEY"):
            try:
                from openai import OpenAI
                model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
                response = OpenAI().embeddings.create(model=model, input=texts)
                self.provider, self.model, self.last_error = "openai", model, None
                return [item.embedding for item in response.data]
            except Exception as exc:
                self.last_error = {"type": type(exc).__name__, "message": str(exc)}
                log.exception("embedding request failed", extra={"model": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")})
        self.provider, self.model = "local-fallback", "local-hash-256"
        return [_local_embedding(text) for text in texts]

    def search(self, query, limit=5, filters: dict | None = None):
        q = self._embed([query])[0]
        filters = filters or {}
        candidates = [d for d in self.documents if all(str(d.metadata.get(k)) == str(v) for k,v in filters.items())]
        scored = [{"score": round(sum(a*b for a,b in zip(q, d.vector)), 4), "id": d.id,
                   "text": d.text, "metadata": d.metadata} for d in candidates]
        return sorted(scored, key=lambda x: x["score"], reverse=True)[:limit]

def records_from_workbook(data):
    records = []
    for sheet, rows in data.rows.items():
        for index, row in enumerate(rows, 2):
            stage = row.get("Stage", "Unassigned")
            safe = {protect_workbook_text(k): protect_workbook_text(v) for k,v in row.items()}
            text = "; ".join(f"{key}: {value}" for key, value in safe.items() if value not in (None, ""))
            records.append({"id": f"{sheet}:{index}", "text": f"{sheet} | {stage} | {text}",
                            "metadata": {"sheet": sheet, "row": index, "stage": stage, "date": row.get("Date"), "source": data.source}})
    return records

