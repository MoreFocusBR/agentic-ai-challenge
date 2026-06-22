import time

from openai import AsyncOpenAI

from app.config import settings
from app.database.connection import get_pool
from app import audit

_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def embed_query(text: str) -> list[float]:
    """Gera o embedding da pergunta do usuário."""
    start = time.monotonic()
    audit.log("rag.embed.start", text_length=len(text), model=settings.embedding_model)

    resp = await _client.embeddings.create(input=text, model=settings.embedding_model)

    tokens = resp.usage.total_tokens if resp.usage else None
    audit.log("rag.embed.complete", duration_ms=audit.ms(start), tokens=tokens)
    return resp.data[0].embedding


async def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """Busca semântica no pgvector. Retorna os chunks mais relevantes."""
    start = time.monotonic()
    audit.log("rag.retrieve.start", query=query, top_k=top_k)

    embedding = await embed_query(query)
    vector_str = "[" + ",".join(map(str, embedding)) + "]"

    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT chunk_id, section, question, content, metadata,
               1 - (embedding <=> $1::vector) AS similarity
        FROM kb_documents
        ORDER BY embedding <=> $1::vector
        LIMIT $2;
        """,
        vector_str,
        top_k,
    )
    results = [dict(r) for r in rows]

    top_sim = round(float(results[0]["similarity"]), 3) if results else None
    min_sim = round(float(results[-1]["similarity"]), 3) if results else None
    audit.log(
        "rag.retrieve.complete",
        results=len(results),
        top_similarity=top_sim,
        min_similarity=min_sim,
        duration_ms=audit.ms(start),
    )
    return results
