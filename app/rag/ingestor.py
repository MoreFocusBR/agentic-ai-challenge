"""
Ingestão programática de documentos para a base de conhecimento.
Demonstra chunking + embeddings + indexação no pgvector.
"""
import uuid
import json
from openai import AsyncOpenAI
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import settings
from app.database.connection import get_pool

_client = AsyncOpenAI(api_key=settings.openai_api_key)


async def ingest_text(text: str, source: str, section: str = "geral") -> int:
    """Faz chunking, gera embeddings e insere no pgvector."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=100, separators=["\n\n", "\n", ". ", " "]
    )
    chunks = splitter.split_text(text)

    pool = await get_pool()
    inserted = 0
    for i, chunk in enumerate(chunks):
        resp = await _client.embeddings.create(
            input=chunk, model=settings.embedding_model
        )
        embedding = resp.data[0].embedding
        vector_str = "[" + ",".join(map(str, embedding)) + "]"

        await pool.execute(
            """
            INSERT INTO kb_documents (id, chunk_id, section, content, embedding, metadata)
            VALUES ($1, $2, $3, $4, $5::vector, $6)
            ON CONFLICT (chunk_id) DO UPDATE
                SET content = EXCLUDED.content, embedding = EXCLUDED.embedding;
            """,
            str(uuid.uuid4()),
            f"{source}-{i}",
            section,
            chunk,
            vector_str,
            json.dumps({"source": source, "section": section}),
        )
        inserted += 1
    return inserted
