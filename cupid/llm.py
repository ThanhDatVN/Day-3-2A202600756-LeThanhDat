"""
Lớp gọi OpenAI dùng chung (chat JSON / chat text / embeddings) + log JSON.

Self-contained: chỉ phụ thuộc openai + stdlib, có telemetry token/latency để
phân tích sau.
"""
import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from openai import OpenAI

from cupid import config

_client: Optional[OpenAI] = None
_LOG_DIR = "logs"


def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def log(event: str, data: Dict[str, Any]) -> None:
    os.makedirs(_LOG_DIR, exist_ok=True)
    path = os.path.join(_LOG_DIR, f"cupid-{datetime.now().strftime('%Y-%m-%d')}.log")
    payload = {"timestamp": datetime.utcnow().isoformat(), "event": event, "data": data}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _track(model: str, usage, latency_ms: int, kind: str) -> None:
    log("LLM_METRIC", {"model": model, "kind": kind,
        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
        "completion_tokens": getattr(usage, "completion_tokens", 0),
        "total_tokens": getattr(usage, "total_tokens", 0),
        "latency_ms": latency_ms})


def chat_json(system: str, user: str, model: Optional[str] = None) -> Dict[str, Any]:
    """Gọi chat, ép trả JSON object (response_format)."""
    model = model or config.CHAT_MODEL
    t0 = time.time()
    resp = client().chat.completions.create(
        model=model, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": user}])
    _track(model, resp.usage, int((time.time() - t0) * 1000), "chat_json")
    return json.loads(resp.choices[0].message.content or "{}")


def chat_text(system: str, user: str, model: Optional[str] = None) -> str:
    model = model or config.CHAT_MODEL
    t0 = time.time()
    resp = client().chat.completions.create(
        model=model, messages=[{"role": "system", "content": system},
                                {"role": "user", "content": user}])
    _track(model, resp.usage, int((time.time() - t0) * 1000), "chat_text")
    return (resp.choices[0].message.content or "").strip()


def embed(texts: List[str], model: Optional[str] = None) -> List[List[float]]:
    model = model or config.EMBED_MODEL
    t0 = time.time()
    resp = client().embeddings.create(model=model, input=texts)
    log("EMBED_METRIC", {"model": model, "n": len(texts),
        "latency_ms": int((time.time() - t0) * 1000)})
    return [d.embedding for d in resp.data]
