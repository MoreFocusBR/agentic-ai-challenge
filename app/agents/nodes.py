# Arquivo mantido por compatibilidade.
# O agente ReAct (create_react_agent) substituiu o StateGraph manual com nós
# retrieve → reason → postprocess → save_memory.
# A lógica de RAG e PDF agora vive em app/tools/agent_tools.py.
# A persistência de memória é feita diretamente em app/api/routes.py.
