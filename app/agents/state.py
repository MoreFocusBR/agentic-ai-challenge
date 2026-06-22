from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Estado compartilhado entre os nós do grafo."""
    messages: Annotated[list, add_messages]
    session_id: str
    user_message: str
    context: str
    sources: list[dict]
    response: str
    pdf_url: str | None
