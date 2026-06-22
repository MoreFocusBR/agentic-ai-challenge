"""
Agente ReAct construído com create_react_agent (LangGraph prebuilt).

Melhorias aplicadas em relação ao StateGraph original:
- Padrão agêntico real: LLM decide quando chamar buscar_conhecimento e gerar_pdf
- ChatPromptTemplate + MessagesPlaceholder (substituí string.replace manual)
- llm.with_retry() contra erros transientes da OpenAI (RateLimit, Timeout, Connection)
"""
from pathlib import Path

import openai
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent

from app.config import settings
from app.tools.agent_tools import buscar_conhecimento, gerar_pdf

_SYSTEM = Path("app/prompts/system_prompt.txt").read_text(encoding="utf-8")

_TOOLS = [buscar_conhecimento, gerar_pdf]

_prompt = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM),
    MessagesPlaceholder("messages"),
])

# bind_tools primeiro; with_retry depois — create_react_agent exige bind_tools aplicado
# antes do wrap RunnableRetry (que não herda BaseChatModel).
_llm_with_tools = (
    ChatOpenAI(
        model=settings.llm_model,
        temperature=0.3,
        api_key=settings.openai_api_key,
    )
    .bind_tools(_TOOLS)
    .with_retry(
        retry_if_exception_type=(
            openai.RateLimitError,
            openai.APITimeoutError,
            openai.APIConnectionError,
        ),
        stop_after_attempt=3,
        wait_exponential_jitter=True,
    )
)


def build_graph():
    return create_react_agent(
        model=_llm_with_tools,
        tools=_TOOLS,
        prompt=_prompt,
    )


graph = build_graph()
