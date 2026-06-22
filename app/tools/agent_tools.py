"""
Ferramentas LangChain (@tool) disponíveis para o agente ReAct.

O marcador %%SOURCES%%...%%END%% é incluído na saída da ferramenta de busca
para que routes.py possa extrair metadados estruturados sem reprocessar a chamada.
O LLM (GPT-4o) ignora o marcador e usa apenas o texto do contexto.
"""
import json

from langchain_core.tools import tool

from app.rag.retriever import retrieve
from app.tools.pdf_generator import generate_pdf as _generate_pdf


@tool
async def buscar_conhecimento(query: str) -> str:
    """Busca informações sobre produtos e soluções da Implanta Soluções na base de conhecimento.

    Use SEMPRE que precisar responder perguntas sobre: CRM, Siscaf, Fiscalização,
    Processos, Sisdoc, Serviços Online, Visão Nacional, Compras & Contratos,
    Licitações, Sialm, Sispat, Sispad, Agenda Financeira, Gestão TCU,
    Portal da Transparência e Siscont.

    Args:
        query: Pergunta ou termo de busca em linguagem natural.
    """
    docs = await retrieve(query, top_k=3)
    if not docs:
        return "Nenhuma informação relevante encontrada para esta consulta."

    parts = [f"[{d['section']}]\n{d['content']}" for d in docs]
    context = "\n\n---\n\n".join(parts)

    sources = [
        {
            "chunk_id": d["chunk_id"],
            "section": d["section"],
            "question": d["question"],
            "similarity": round(float(d["similarity"]), 3),
        }
        for d in docs
    ]
    return f"{context}\n\n%%SOURCES%%{json.dumps(sources, ensure_ascii=False)}%%END%%"


@tool
def gerar_pdf(titulo: str, conteudo: str) -> str:
    """Gera um documento PDF com título e conteúdo e retorna o link para download.

    Use SOMENTE quando o usuário solicitar explicitamente a criação de um
    relatório ou documento em PDF.

    Args:
        titulo: Título do documento PDF (até 200 caracteres).
        conteudo: Conteúdo completo do documento.
    """
    filename = _generate_pdf(titulo, conteudo)
    return f"PDF gerado com sucesso. Link para download: /documents/{filename}"
