import asyncio
import io
import json
import os
import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.messages import HumanMessage, AIMessage
from pydantic import BaseModel, Field
from pypdf import PdfReader

from app.config import settings
from app.security import verify_api_key, sanitize_input, sanitize_output
from app.agents.graph import graph
from app.memory.checkpointer import load_history, append_to_history
from app.rag.ingestor import ingest_text
from app.tools.pdf_generator import generate_pdf

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: str = Field(default="default", max_length=100)
    message: str = Field(..., max_length=2000)


class ChatResponse(BaseModel):
    response: str
    sources: list[dict]
    pdf_url: str | None = None
    session_id: str


class PdfRequest(BaseModel):
    title: str = Field(..., max_length=200)
    content: str = Field(..., max_length=20000)


def _extract_from_messages(messages: list) -> tuple[list[dict], str | None]:
    """Extrai sources e pdf_url das ToolMessages do agente ReAct."""
    sources: list[dict] = []
    pdf_url: str | None = None
    for msg in messages:
        name = getattr(msg, "name", None)
        content = getattr(msg, "content", "") or ""
        if name == "buscar_conhecimento":
            m = re.search(r"%%SOURCES%%(.*?)%%END%%", content, re.DOTALL)
            if m:
                try:
                    sources = json.loads(m.group(1))
                except Exception:
                    pass
        elif name == "gerar_pdf":
            m = re.search(r"/documents/[\w\-]+\.pdf", content)
            if m:
                pdf_url = m.group(0)
    return sources, pdf_url


async def _build_messages(session_id: str, user_message: str) -> list:
    """Carrega histórico do PostgreSQL e monta lista de mensagens LangChain."""
    history = await load_history(session_id)
    messages: list = []
    for entry in history:
        role = entry.get("type", "")
        content = entry.get("content", "")
        if role == "human":
            messages.append(HumanMessage(content=content))
        elif role == "ai":
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_message))
    return messages


@router.post("/chat", response_model=ChatResponse, dependencies=[Depends(verify_api_key)])
async def chat(req: ChatRequest):
    clean_message = sanitize_input(req.message)
    messages = await _build_messages(req.session_id, clean_message)

    try:
        result = await asyncio.wait_for(
            graph.ainvoke({"messages": messages}),
            timeout=settings.agent_timeout,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"O agente não respondeu dentro do limite de {settings.agent_timeout}s. Tente novamente.",
        )

    final_msg = result["messages"][-1]
    response_text = sanitize_output(getattr(final_msg, "content", "") or "")
    if not response_text:
        response_text = (
            "Não encontrei informações suficientes. "
            "Recomendo contato direto com a Implanta."
        )

    sources, pdf_url = _extract_from_messages(result["messages"])

    await append_to_history(req.session_id, "human", clean_message)
    await append_to_history(req.session_id, "ai", response_text)

    return ChatResponse(
        response=response_text,
        sources=sources,
        pdf_url=pdf_url,
        session_id=req.session_id,
    )


@router.post("/chat/stream", dependencies=[Depends(verify_api_key)])
async def chat_stream(req: ChatRequest):
    """Endpoint SSE: transmite tokens da resposta final em tempo real."""
    clean_message = sanitize_input(req.message)
    messages = await _build_messages(req.session_id, clean_message)

    async def generate():
        full_response = ""
        all_messages: list = []
        try:
            async for event in graph.astream_events({"messages": messages}, version="v2"):
                kind = event["event"]
                if kind == "on_chat_model_stream":
                    chunk = event["data"]["chunk"]
                    token = chunk.content if hasattr(chunk, "content") else ""
                    if token:
                        full_response += token
                        yield f"data: {json.dumps({'delta': token}, ensure_ascii=False)}\n\n"
                elif kind == "on_chain_end" and event.get("name") == "LangGraph":
                    output = event["data"].get("output", {})
                    all_messages = output.get("messages", [])
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
            return

        final = sanitize_output(full_response)
        await append_to_history(req.session_id, "human", clean_message)
        await append_to_history(req.session_id, "ai", final)

        sources, pdf_url = _extract_from_messages(all_messages)
        yield f"data: {json.dumps({'done': True, 'sources': sources, 'pdf_url': pdf_url}, ensure_ascii=False)}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


@router.post("/generate-pdf", dependencies=[Depends(verify_api_key)])
async def generate_pdf_endpoint(req: PdfRequest):
    filename = generate_pdf(req.title, req.content)
    return {"filename": filename, "pdf_url": f"/documents/{filename}"}


@router.post("/ingest-pdf", dependencies=[Depends(verify_api_key)])
async def ingest_pdf(
    file: UploadFile = File(...),
    section: str = Form(default="geral"),
    source: str = Form(default=""),
):
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Envie um arquivo .pdf válido.")
    if file.size and file.size > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Arquivo muito grande (limite: 20 MB).")

    raw = await file.read()
    try:
        reader = PdfReader(io.BytesIO(raw))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        full_text = "\n\n".join(p for p in pages_text if p.strip())
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Não foi possível ler o PDF: {exc}")

    if not full_text.strip():
        raise HTTPException(status_code=422, detail="O PDF não contém texto extraível (pode ser escaneado/imagem).")

    src = source.strip() or os.path.splitext(file.filename)[0]
    chunks = await ingest_text(full_text, source=src, section=section.strip() or "geral")
    return {"chunks": chunks, "pages": len(reader.pages), "source": src, "section": section}


@router.get("/documents/{arquivo}", dependencies=[Depends(verify_api_key)])
async def download(arquivo: str):
    if "/" in arquivo or "\\" in arquivo or ".." in arquivo:
        raise HTTPException(status_code=400, detail="Nome de arquivo inválido.")
    filepath = os.path.join(settings.documents_dir, arquivo)
    if not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="Documento não encontrado.")
    return FileResponse(filepath, media_type="application/pdf", filename=arquivo)
