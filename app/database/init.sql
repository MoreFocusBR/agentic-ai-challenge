-- Habilita a extensão pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabela da base de conhecimento (RAG)
CREATE TABLE IF NOT EXISTS kb_documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id    TEXT UNIQUE NOT NULL,
    section     TEXT,
    question    TEXT,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Índice HNSW para busca por similaridade de cosseno.
-- Funciona bem em qualquer tamanho de dataset (ao contrário do ivfflat).
CREATE INDEX IF NOT EXISTS kb_documents_embedding_idx
    ON kb_documents USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Tabela de memória conversacional (compatível com N8N Postgres Chat Memory)
CREATE TABLE IF NOT EXISTS n8n_chat_histories (
    id          SERIAL PRIMARY KEY,
    session_id  TEXT NOT NULL,
    message     JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS n8n_chat_histories_session_idx
    ON n8n_chat_histories(session_id);
