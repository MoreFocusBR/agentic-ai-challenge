from openai import AsyncOpenAI
from app.config import settings
from app.database.connection import get_pool

_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def embed_query(text: str) -> list[float]:
    """Gera o embedding da pergunta do usuário."""
    resp = await _client.embeddings.create(
        input=text, model=settings.embedding_model
    )
    return resp.data[0].embedding


async def retrieve(query: str, top_k: int = 3) -> list[dict]:
    """Busca semântica no pgvector. Retorna os chunks mais relevantes."""
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
    return [dict(r) for r in rows]
