"""
Audit logger — emite eventos estruturados (ndjson) para rastreabilidade completa.

Cada linha de log é um objeto JSON com:
  ts        — timestamp ISO-8601 UTC com milissegundos
  trace     — ID hexadecimal da requisição HTTP (12 chars), propagado via ContextVar
  event     — nome do evento (ex: "rag.retrieve.complete")
  ...campos — metadados livres do evento

Uso:
    from app import audit

    audit.log("rag.retrieve.start", query=q, top_k=3)
    start = time.monotonic()
    ...
    audit.log("rag.retrieve.complete", results=5, duration_ms=audit.ms(start))
"""
import json
import logging
import time
from contextvars import ContextVar
from datetime import datetime, timezone

# Trace ID por requisição HTTP — propagado pelo AuditMiddleware em main.py.
_trace_id: ContextVar[str] = ContextVar("trace_id", default="-")


def set_trace(tid: str) -> None:
    _trace_id.set(tid)


def get_trace() -> str:
    return _trace_id.get()


def ms(start: float) -> int:
    """Milissegundos desde `start` (time.monotonic())."""
    return round((time.monotonic() - start) * 1000)


# Logger dedicado — não propaga para o root logger para evitar duplicatas.
_logger = logging.getLogger("audit")
if not _logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_h)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def log(event: str, **fields) -> None:
    """Emite um evento de auditoria como linha JSON."""
    now = datetime.now(timezone.utc)
    record = {
        "ts": now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z",
        "trace": _trace_id.get(),
        "event": event,
        **fields,
    }
    _logger.info(json.dumps(record, ensure_ascii=False, default=str))
