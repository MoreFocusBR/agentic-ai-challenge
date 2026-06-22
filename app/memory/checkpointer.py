"""
Memória conversacional persistente via PostgreSQL.

Usa a tabela n8n_chat_histories — mesma estrutura do N8N Postgres Chat Memory,
garantindo compatibilidade entre as duas implementações (N8N e Python/LangGraph).

Escolha de tecnologia: PostgreSQL (sem dependência extra de Redis ou cache).
Motivo: o banco já está provisionado para o RAG; reutilizá-lo simplifica a
infraestrutura e mantém a memória persistente entre reinicializações do servidor.
"""
import json

from app.database.connection import get_pool
from app import audit


async def load_history(session_id: str, max_pairs: int = 5) -> list[dict]:
    """
    Retorna até `max_pairs` pares (human, ai) mais recentes da sessão,
    em ordem cronológica, prontos para serem usados como mensagens LangChain.
    """
    pool = await get_pool()
    rows = await pool.fetch(
        """
        SELECT message FROM n8n_chat_histories
        WHERE session_id = $1
        ORDER BY created_at DESC
        LIMIT $2
        """,
        session_id,
        max_pairs * 2,
    )
    messages = []
    for row in reversed(rows):
        raw = row["message"]
        messages.append(json.loads(raw) if isinstance(raw, str) else raw)

    audit.log("memory.load", session_id=session_id, messages_returned=len(messages))
    return messages


async def append_to_history(session_id: str, role: str, content: str) -> None:
    """Persiste uma mensagem individual no histórico."""
    pool = await get_pool()
    await pool.execute(
        """
        INSERT INTO n8n_chat_histories (session_id, message)
        VALUES ($1, $2)
        """,
        session_id,
        json.dumps({"type": role, "content": content}),
    )
    audit.log("memory.append", session_id=session_id, role=role, content_len=len(content))
