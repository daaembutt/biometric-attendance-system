import os
from typing import List, Tuple, Optional

import cv2
import numpy as np

try:
    from .config import INSIGHTFACE_MODEL, INSIGHTFACE_DET_SIZE
except Exception:
    INSIGHTFACE_MODEL = os.environ.get("INSIGHTFACE_MODEL", "buffalo_l")
    INSIGHTFACE_DET_SIZE = int(os.environ.get("INSIGHTFACE_DET_SIZE", "640"))


def _ensure_insightface_detector():
    """Lazy import so the rest of the app can start even if insightface missing."""
    import insightface
    from insightface.app import FaceAnalysis

    app = FaceAnalysis(name=INSIGHTFACE_MODEL, providers=["CPUExecutionProvider"])
    # det_size is supported in most versions; keep safe fallback
    try:
        app.prepare(ctx_id=-1, det_size=(INSIGHTFACE_DET_SIZE, INSIGHTFACE_DET_SIZE))
    except TypeError:
        app.prepare(ctx_id=-1)
    return app


_detector = None


def get_face_embedding(frame_bgr: np.ndarray) -> Tuple[List[Tuple[int,int,int,int]], List[np.ndarray]]:
    """Return (boxes, embeddings) for all faces found.

    embeddings are L2-normalized float32 vectors.
    """
    global _detector
    if _detector is None:
        _detector = _ensure_insightface_detector()

    # insightface expects BGR images
    faces = _detector.get(frame_bgr)
    boxes = []
    embs = []
    if not faces:
        return boxes, embs

    h, w = frame_bgr.shape[:2]
    for f in faces:
        x1, y1, x2, y2 = f.bbox.astype(int)
        x1 = max(0, x1); y1 = max(0, y1)
        x2 = min(w - 1, x2); y2 = min(h - 1, y2)
        boxes.append((x1, y1, x2, y2))

        emb = getattr(f, "embedding", None)
        if emb is None:
            continue
        emb = np.asarray(emb, dtype=np.float32)
        norm = np.linalg.norm(emb)
        if norm > 0:
            emb = emb / norm
        embs.append(emb)

    return boxes, embs


def embedding_to_bytes(emb: np.ndarray) -> bytes:
    emb = np.asarray(emb, dtype=np.float32)
    return emb.tobytes()


def bytes_to_embedding(b: bytes) -> np.ndarray:
    """Decode float32 embedding bytes.

    Stored embedding dimension depends on model; we infer by length.
    """
    arr = np.frombuffer(b, dtype=np.float32)
    return arr


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine distance with dimension-safety.

    Your stored embeddings and live embeddings must have the same length.
    If they don't, we treat it as a non-match (distance = 1.0).
    """
    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)

    if a.ndim != 1:
        a = a.reshape(-1)
    if b.ndim != 1:
        b = b.reshape(-1)

    if a.shape[0] != b.shape[0]:
        # Prevent ValueError: shapes not aligned
        return 1.0

    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 1.0

    sim = float(np.dot(a, b) / denom)
    return 1.0 - sim


