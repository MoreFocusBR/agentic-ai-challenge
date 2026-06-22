import re
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

from app.config import settings
from app import audit

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_INJECTION_PATTERNS = [
    ("ignore_previous",   re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts?)", re.I)),
    ("disregard",         re.compile(r"disregard\s+(all\s+)?(previous|prior|above)", re.I)),
    ("forget_instructions", re.compile(r"forget\s+(everything|all|your\s+instructions)", re.I)),
    ("you_are_now",       re.compile(r"you\s+are\s+now\s+(a|an)\s+", re.I)),
    ("reveal_prompt",     re.compile(r"reveal\s+your\s+(system\s+)?(prompt|instructions)", re.I)),
    ("jailbreak",         re.compile(r"jailbreak", re.I)),
    ("developer_mode",    re.compile(r"developer\s+mode", re.I)),
    ("DAN",               re.compile(r"\bDAN\b")),
]


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """Autenticação via API Key no header X-API-Key."""
    if not api_key or api_key != settings.auth_api_key:
        audit.log("auth.fail", reason="invalid_or_missing_key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key inválida ou ausente.",
        )
    audit.log("auth.ok", key_prefix=api_key[:4] + "***")
    return api_key


def sanitize_input(text: str) -> str:
    """Valida e sanitiza a entrada do usuário."""
    if not text or not isinstance(text, str):
        raise HTTPException(status_code=400, detail="Mensagem inválida.")

    cleaned = text.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="Mensagem vazia.")
    if len(cleaned) > 2000:
        raise HTTPException(status_code=400, detail="Mensagem excede 2000 caracteres.")

    cleaned = re.sub(r"<[^>]*>", "", cleaned)
    cleaned = re.sub(r"[\x00-\x1F\x7F]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    for name, pattern in _INJECTION_PATTERNS:
        if pattern.search(cleaned):
            audit.log("input.blocked", pattern=name, input_length=len(text))
            raise HTTPException(
                status_code=400,
                detail="Conteúdo bloqueado: possível tentativa de manipulação.",
            )

    audit.log("input.sanitized", original_len=len(text), clean_len=len(cleaned))
    return cleaned


def sanitize_output(text: str) -> str:
    """Sanitização básica da resposta da LLM."""
    cleaned = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.I | re.S)
    return cleaned.strip()
