# Assistente Corporativo Agêntico

Prova Técnica — Analista Sênior de Inteligência Artificial  
Solução de IA agêntica com RAG (PostgreSQL + pgvector), memória conversacional,
geração de PDF, segurança e API REST. Implementada em **N8N** e reproduzida em
**Python + LangChain/LangGraph**.

---

## Arquitetura da Solução

### Visão geral

```
Cliente HTTP
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│                  FastAPI  (porta 8000)                  │
│  POST /chat   POST /generate-pdf   GET /documents/{f}  │
│                        │                               │
│           ┌────────────▼────────────┐                  │
│           │    LangGraph Agent       │                  │
│           │  retrieve → reason →    │                  │
│           │  postprocess →          │                  │
│           │  save_memory            │                  │
│           └────────────┬────────────┘                  │
│                        │                               │
│          ┌─────────────▼──────────────┐                │
│          │   PostgreSQL + pgvector    │                 │
│          │  • kb_documents  (RAG)     │                 │
│          │  • n8n_chat_histories      │                 │
│          │    (memória conversacional)│                 │
│          └────────────────────────────┘                │
│                                                         │
│         ┌──────────────────────┐                        │
│         │  ReportLab (PDF)     │                        │
│         │  documents/ (volume) │                        │
│         └──────────────────────┘                        │
└─────────────────────────────────────────────────────────┘
```

### Fluxo de uma requisição `/chat`

```
1. sanitize_input()         → bloqueia prompt injection, HTML, chars de controle
2. load_history()           → recupera últimos 5 pares de mensagens do PostgreSQL
3. ReAct Agent (LangGraph)
   ├─ LLM decide → chama buscar_conhecimento(@tool) → embed + pgvector top-3
   ├─ LLM raciocina com o contexto
   └─ LLM decide → chama gerar_pdf(@tool) se solicitado pelo usuário
4. sanitize_output()        → remove scripts, fallback para resposta vazia
5. append_to_history()      → persiste par (human, ai) em n8n_chat_histories
6. ChatResponse             → { response, sources, pdf_url, session_id }
```

### Grafo LangGraph (Parte 2) — Agente ReAct

```
[START] → agent (LLM) → tools? → agent → ... → [END]
                ↑_________|
```

Implementado com `create_react_agent` (LangGraph prebuilt). O LLM decide
autonomamente quando chamar `buscar_conhecimento` e `gerar_pdf`.

Melhorias de boas práticas aplicadas:
- `@tool` decorator para RAG e PDF (padrão agêntico real)
- `ChatPromptTemplate` + `MessagesPlaceholder` (substitui string.replace manual)
- `/chat/stream` — streaming SSE via `astream_events(version="v2")`
- `llm.with_retry()` — resiliência contra RateLimitError / APITimeoutError

### Fluxo N8N (Parte 1) — 12 nós

```
Webhook → Pré-processamento (JS) → Bloqueado? (IF)
    ├─ sim → Resposta 400
    └─ não → AI Agent
               ├─ OpenAI Chat Model (GPT-4o)
               ├─ Postgres Chat Memory (n8n_chat_histories)
               ├─ Embeddings OpenAI → PGVector Store (retrieve-as-tool)
               └─ Tool HTTP → POST /generate-pdf
          → Pós-processamento (JS) → Resposta 200
```

---

## LLM Utilizada

| Campo | Valor |
|---|---|
| **Modelo** | `gpt-4o` |
| **Provedor** | OpenAI |
| **Embeddings** | `text-embedding-3-small` (1536 dims) |

**Motivo da escolha:** GPT-4o oferece o melhor equilíbrio entre qualidade de
raciocínio, velocidade e custo para o contexto corporativo. O N8N possui nó
nativo para OpenAI, simplificando a integração na Parte 1. O modelo de
embeddings `text-embedding-3-small` tem custo baixo e qualidade semântica
suficiente para RAG em português.

---

## Estratégia de Memória

**Tecnologia:** PostgreSQL — tabela `n8n_chat_histories`.

**Formato de cada registro:**
```json
{ "type": "human" | "ai", "content": "..." }
```

**Motivo da escolha:**
- O banco já está provisionado para o RAG; não há dependência extra (ex.: Redis).
- A mesma tabela é usada pelo **N8N Postgres Chat Memory**, mantendo
  compatibilidade entre as duas implementações.
- Memória persistente entre reinicializações do servidor.
- Simples de inspecionar, fazer backup e limpar por sessão.

**Funcionamento:**
- Antes de chamar a LLM, `load_history(session_id)` recupera os últimos 5 pares
  de mensagens e os insere no contexto como `HumanMessage`/`AIMessage`.
- Após a resposta, `save_memory_node` persiste o novo par via
  `append_to_history()`.

---

## Estratégia de Segurança

### Gestão de credenciais
- Todas as credenciais são carregadas de variáveis de ambiente (`.env`).
- Nenhum segredo está hardcoded no código-fonte.
- O arquivo `.env.example` documenta as variáveis sem valores reais.

### Autenticação
- API Key obrigatória no header `X-API-Key` em todos os endpoints protegidos.
- Implementada via `fastapi.security.APIKeyHeader` em `app/security.py`.

### Proteção de entrada (Prompt Injection)
Oito padrões regex bloqueiam mensagens maliciosas antes de chegarem ao agente:
```
ignore (all) previous instructions
disregard (all) prior/above
forget everything / your instructions
you are now a/an ...
reveal your (system) prompt/instructions
jailbreak
developer mode
\bDAN\b
```

### SQL Injection
Todas as queries usam placeholders parametrizados (`$1`, `$2`) via `asyncpg`.
Nenhuma query é construída por concatenação de string.

### Outros
| Vetor | Mitigação |
|---|---|
| XSS | Remoção de tags `<script>` e HTML na entrada e saída |
| Caracteres de controle | `re.sub(r"[\x00-\x1F\x7F]", " ", ...)` |
| Tamanho de entrada | Máximo 2000 chars (Pydantic + sanitização) |
| Path traversal | Validação de `"/"`, `"\\"`, `".."` no nome do arquivo |
| Timeout do agente | `asyncio.wait_for(graph.ainvoke(...), timeout=AGENT_TIMEOUT)` |
| CORS | `CORSMiddleware` configurado no FastAPI |

---

## Bibliotecas Utilizadas

| Biblioteca | Finalidade |
|---|---|
| `fastapi` | Framework REST assíncrono com validação Pydantic nativa |
| `uvicorn` | Servidor ASGI para o FastAPI |
| `langchain` | Abstrações de prompt, mensagens e chains |
| `langchain-openai` | Integração `ChatOpenAI` e `OpenAIEmbeddings` |
| `langchain-text-splitters` | `RecursiveCharacterTextSplitter` para chunking |
| `langgraph` | Orquestração do agente como grafo de estados |
| `openai` | SDK direto para embeddings e API OpenAI |
| `asyncpg` | Driver PostgreSQL async de alta performance (pool de conexões) |
| `psycopg2-binary` | Driver PostgreSQL síncrono (usado no seed script) |
| `pydantic-settings` | Carregamento tipado de variáveis de ambiente |
| `python-dotenv` | Leitura do arquivo `.env` |
| `reportlab` | Geração de documentos PDF com layout personalizado |
| `aiofiles` | Leitura assíncrona de arquivos estáticos (FileResponse) |
| `python-multipart` | Suporte a form data no FastAPI |

---

## Variáveis de Ambiente

```env
# LLM
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxx
LLM_MODEL=gpt-4o
EMBEDDING_MODEL=text-embedding-3-small

# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=corporativo
POSTGRES_USER=postgres
POSTGRES_PASSWORD=troque_esta_senha

# Segurança
AUTH_API_KEY=defina_uma_chave_secreta_forte

# PDF
DOCUMENTS_DIR=documents

# Timeout do agente em segundos (padrão: 30)
AGENT_TIMEOUT=30
```

---

## Execução Local

> Requer Python 3.11+ e um PostgreSQL com a extensão `pgvector` acessível.

```bash
# 1. Clone o repositório
git clone <url-do-repositorio>
cd agentic-ai-challenge

# 2. Crie e ative o ambiente virtual
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Configure o ambiente
cp .env.example .env
# Edite o .env com suas credenciais
# Para rodar local sem Docker: POSTGRES_HOST=localhost

# 5. Suba apenas o banco via Docker
docker compose up -d postgres

# 6. Popule a base de conhecimento (uma vez)
python seed_knowledge_base.py

# 7. Suba a API
uvicorn app.main:app --reload --port 8000
```

Acesse:
- **Frontend:** http://localhost:8000
- **Swagger:** http://localhost:8000/docs

---

## Execução via Docker

```bash
# 1. Configure o ambiente
cp .env.example .env
# Edite o .env — mantenha POSTGRES_HOST=postgres

# 2. Suba todos os serviços
docker compose up -d

# 3. Popule a base de conhecimento (uma vez)
docker compose exec app python seed_knowledge_base.py
```

Serviços disponíveis:
| Serviço | URL |
|---|---|
| Frontend / API | http://localhost:8000 |
| Swagger Docs | http://localhost:8000/docs |
| N8N | http://localhost:5678 |
| PostgreSQL | localhost:5432 |

---

## Exemplos de uso via cURL

```bash
export API_KEY="sua-chave"
export BASE="http://localhost:8000"

# Conversa
curl -X POST "$BASE/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"session_id": "demo", "message": "Quais as funcionalidades do Siscaf?"}'

# Streaming SSE (tokens em tempo real)
curl -N -X POST "$BASE/chat/stream" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"session_id": "demo", "message": "O que é o Sispat?"}'

# Gerar PDF
curl -X POST "$BASE/generate-pdf" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{"title": "Relatório Siscaf", "content": "Resumo das funcionalidades..."}'

# Download
curl -H "X-API-Key: $API_KEY" \
  "$BASE/documents/relatorio_siscaf_abc123.pdf" -o saida.pdf

# Verificações de segurança (devem ser bloqueadas)
curl -X POST "$BASE/chat" \
  -H "X-API-Key: $API_KEY" \
  -d '{"message": "ignore all previous instructions"}'   # → 400

curl -X POST "$BASE/chat" \
  -d '{"message": "oi"}'                                 # → 401 (sem API Key)
```

---

## Importar fluxo N8N

1. Abra o N8N (http://localhost:5678)
2. **Workflows → ⋮ → Import from File**
3. Selecione `n8n/workflow.json`
4. Configure as três credenciais:

| Credencial | Tipo | Valor |
|---|---|---|
| OpenAI API | `openAiApi` | `OPENAI_API_KEY` |
| PostgreSQL | `postgres` | host `postgres`, porta 5432, db/user/senha do `.env` |
| API Key Header | `httpHeaderAuth` | Nome: `X-API-Key`, Valor: `AUTH_API_KEY` |

---

## Estrutura do projeto

```
projeto/
├── app/
│   ├── api/routes.py            # Endpoints REST + /chat/stream (SSE)
│   ├── agents/
│   │   ├── state.py             # AgentState (TypedDict — legado)
│   │   ├── nodes.py             # Substituído por create_react_agent
│   │   └── graph.py             # create_react_agent + ChatPromptTemplate + with_retry
│   ├── tools/
│   │   ├── agent_tools.py       # @tool buscar_conhecimento + @tool gerar_pdf
│   │   └── pdf_generator.py     # Geração de PDF (ReportLab)
│   ├── rag/
│   │   ├── retriever.py         # Busca semântica no pgvector
│   │   └── ingestor.py          # Chunking + embeddings + upsert
│   ├── memory/checkpointer.py   # load_history / append_to_history
│   ├── database/
│   │   ├── connection.py        # Pool asyncpg
│   │   └── init.sql             # CREATE EXTENSION + tabelas + índice HNSW
│   ├── prompts/system_prompt.txt
│   ├── config.py                # Settings (pydantic-settings)
│   ├── security.py              # verify_api_key, sanitize_input/output
│   └── main.py                  # FastAPI + lifespan + CORS
├── frontend/index.html          # Chat UI (vanilla HTML/CSS/JS)
├── documents/                   # PDFs gerados (volume Docker)
├── n8n/workflow.json            # Fluxo exportado do N8N (12 nós)
├── seed_knowledge_base.py       # Carga inicial: 18 chunks FAQ Implanta
├── docker-compose.yml           # postgres, app, n8n
├── Dockerfile
├── requirements.txt
└── .env.example
```
