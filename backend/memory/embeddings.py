"""Local semantic embeddings via fastembed (ONNX, no external key).

Model: BAAI/bge-small-en-v1.5 (384-dim). Downloads once, cached on disk.
Similarity is computed in-app with cosine (MongoDB-backed storage).
"""
import asyncio
import numpy as np

from core.logging import logger

_MODEL_NAME = "BAAI/bge-small-en-v1.5"
DIM = 384
_model = None


def _get_model():
    global _model
    if _model is None:
        from fastembed import TextEmbedding
        logger.info("Loading embedding model %s ...", _MODEL_NAME)
        _model = TextEmbedding(model_name=_MODEL_NAME)
        logger.info("Embedding model ready (dim=%d)", DIM)
    return _model


def _embed_sync(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _get_model().embed(texts)]


async def embed(texts: list[str]) -> list[list[float]]:
    return await asyncio.to_thread(_embed_sync, texts)


async def embed_one(text: str) -> list[float]:
    return (await embed([text]))[0]


def cosine(a, b) -> float:
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)
    denom = float(np.linalg.norm(a) * np.linalg.norm(b))
    return 0.0 if denom == 0 else float(np.dot(a, b) / denom)


def warmup():
    """Load model in a background thread so the first request is fast."""
    try:
        _get_model()
    except Exception as e:
        logger.error("Embedding warmup failed: %s", e)
