"""
seed_knowledge_base.py
----------------------
Popula o PostgreSQL + pgvector com o FAQ da Implanta Soluções.
Rode UMA VEZ antes de subir o agente.

Uso:
    pip install openai psycopg2-binary python-dotenv
    python seed_knowledge_base.py
"""

import os
import json
import uuid
import psycopg2
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Config — ajuste via .env ou variáveis de ambiente
# ---------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

PG_HOST     = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT     = os.getenv("POSTGRES_PORT", "5432")
PG_DB       = os.getenv("POSTGRES_DB", "postgres")
PG_USER     = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# ---------------------------------------------------------------------------
# Chunks — FAQ da Implanta Soluções
# Cada chunk = 1 par pergunta + resposta (unidade semântica ideal para RAG)
# ---------------------------------------------------------------------------
CHUNKS = [
    {
        "id": "visao-geral-1",
        "section": "Visão Geral",
        "question": "O que a Implanta oferece?",
        "answer": (
            "A Implanta oferece inovação tecnológica e segurança digital para Conselhos de "
            "Fiscalização Profissional, com uma suíte integrada de soluções especializadas. "
            "Seus sistemas garantem automação, eficiência e conformidade, atendendo às "
            "necessidades administrativas, financeiras e operacionais dos Conselhos."
        ),
    },
    {
        "id": "visao-geral-2",
        "section": "Visão Geral",
        "question": "Para quem são as soluções da Implanta?",
        "answer": (
            "As soluções são destinadas a Conselhos de Fiscalização Profissional que buscam "
            "simplificar processos e assegurar uma administração mais ágil, organizada e estratégica."
        ),
    },
    {
        "id": "crm-1",
        "section": "CRM",
        "question": "O que é o CRM da Implanta e quais são suas principais funcionalidades?",
        "answer": (
            "O CRM da Implanta é uma solução completa para organizar e padronizar o atendimento "
            "ao público dos Conselhos, controlando as interações e gerando respostas rápidas e "
            "precisas. Inclui triagem inteligente de e-mails, status de atendimento em tempo real, "
            "base de conhecimento inteligente (FAQ), registro de chamados, agendamento online de "
            "visitas e integração com Siscaf e Serviços Online."
        ),
    },
    {
        "id": "fiscalizacao-1",
        "section": "Fiscalização",
        "question": "O que é a solução Fiscalização da Implanta e quais são suas funcionalidades?",
        "answer": (
            "É uma solução para Conselhos que buscam controle e transparência nos processos de "
            "fiscalização, automatizando o planejamento e execução de visitas fiscais. Oferece "
            "controle total dos processos, módulo de retaguarda para o Conselho (cadastro de fiscais, "
            "controle de rotas, agendamento) e módulo de campo para o fiscal (registro de "
            "check-ins/check-outs, monitoramento via GPS, emissão de documentos no local, "
            "operação offline)."
        ),
    },
    {
        "id": "processos-1",
        "section": "Processos",
        "question": "O que é a solução Processos da Implanta e quais são suas funcionalidades?",
        "answer": (
            "É uma solução robusta e integrada para a administração de processos éticos, "
            "administrativos e jurídicos nos Conselhos Profissionais, desde o protocolo inicial "
            "até a tramitação final. Permite centralização e organização de processos, "
            "acompanhamento e tramitação eletrônica, digitalização e automação de documentos "
            "(com assinatura digital), e integração com outros módulos Implanta.Net para controle "
            "de prazos, gestão de audiências e relatórios."
        ),
    },
    {
        "id": "siscaf-1",
        "section": "Siscaf",
        "question": "O que é o Siscaf da Implanta e quais são suas funcionalidades?",
        "answer": (
            "O Siscaf é uma solução integrada para a gestão cadastral e financeira de profissionais "
            "e empresas registrados no Conselho, centralizando informações e facilitando transações. "
            "Oferece controle geral de dados cadastrais e financeiros, gestão simplificada de "
            "débitos e pagamentos (com PIX, cartões), segurança e conformidade com a LGPD, "
            "negativação e controle de dívida ativa, emissão de identidades profissionais e "
            "recursos para serviços online."
        ),
    },
    {
        "id": "sisdoc-1",
        "section": "Sisdoc",
        "question": "O que é o Sisdoc da Implanta e quais são suas funcionalidades?",
        "answer": (
            "O Sisdoc é uma solução para o gerenciamento de documentos e protocolos, "
            "proporcionando controle e segurança na administração documental, eliminando o uso "
            "de papel. Inclui controle total sobre documentos e protocolos, digitalização de "
            "documentos físicos, assinatura e autenticação eletrônica com validade jurídica, "
            "integração com Siscaf e Processos, cadastro e classificação de documentos, "
            "tramitação digital, automação de fluxos e alertas automáticos."
        ),
    },
    {
        "id": "servicos-online-1",
        "section": "Serviços Online",
        "question": "O que é a solução Serviços Online da Implanta e quais são suas funcionalidades?",
        "answer": (
            "É uma plataforma web completa para automatizar o atendimento a profissionais, "
            "empresas registradas e ao público em geral, modernizando as interações digitais dos "
            "Conselhos. Oferece acesso mobile e responsivo, consultas públicas e restritivas "
            "personalizadas, gestão completa de pré-cadastro e cadastro, requerimentos online "
            "automatizados e campanhas de pagamento online."
        ),
    },
    {
        "id": "visao-nacional-1",
        "section": "Visão Nacional",
        "question": "O que é o Visão Nacional da Implanta e quais são suas funcionalidades?",
        "answer": (
            "É uma solução para Conselhos Federais que centraliza em um único ambiente nacional "
            "os registros de profissionais e empresas, consolidando informações de diversas fontes "
            "para uma visão unificada da categoria. Permite consultas e estatísticas em âmbito "
            "nacional, relatórios personalizados e webservices, integração com Siscaf e sistemas "
            "terceiros, consulta entre Conselhos Regionais e uma plataforma unificada e segura."
        ),
    },
    {
        "id": "compras-contratos-1",
        "section": "Compras & Contratos",
        "question": "O que é a solução Compras & Contratos da Implanta e quais são suas funcionalidades?",
        "answer": (
            "É uma ferramenta para otimizar e modernizar a gestão de aquisições, cotações de "
            "preços e contratações de serviços, automatizando processos e assegurando conformidade "
            "legal. Oferece administração completa dos processos de compra, monitoramento inteligente "
            "de contratos, integração com sistemas contábeis (Siscont) e Portal da Transparência, "
            "gestão centralizada de aquisições, cotação eletrônica, pedidos online, geração de "
            "ordens de compra e serviço, e assinatura eletrônica de documentos."
        ),
    },
    {
        "id": "licitacoes-1",
        "section": "Licitações",
        "question": "O que é a solução Licitações da Implanta e quais são suas funcionalidades?",
        "answer": (
            "É uma solução para garantir uma gestão completa e segura dos processos licitatórios, "
            "acompanhando todas as fases desde a solicitação inicial até a contratação do fornecedor. "
            "Permite centralização de registros, histórico completo de cada licitação, gestão de "
            "fases e prazos, registro e emissão de julgamento final, vinculação de documentos, "
            "integração orçamentária, gestão de cotações de preços, gerenciamento de ordens de "
            "compras e serviços, e seleção automática da melhor proposta."
        ),
    },
    {
        "id": "sialm-1",
        "section": "Sialm",
        "question": "O que é o Sialm da Implanta e quais são suas funcionalidades?",
        "answer": (
            "O Sialm é uma solução para o gerenciamento preciso e automatizado do almoxarifado "
            "e materiais de consumo de Conselhos, facilitando o controle de solicitações e "
            "acompanhamento de consumo. Inclui gestão inteligente de estoques e materiais, "
            "solicitações digitais e fluxo de aprovação, relatórios e análises estratégicas, "
            "registro e atendimento de pedidos, controle de devoluções e trocas, integração com "
            "Compras & Contratos e lançamentos contábeis automatizados."
        ),
    },
    {
        "id": "sispat-1",
        "section": "Sispat",
        "question": "O que é o Sispat da Implanta e quais são suas funcionalidades?",
        "answer": (
            "O Sispat oferece controle total sobre o ciclo de vida dos bens móveis, imóveis e "
            "intangíveis, automatizando processos como depreciação e lançamentos contábeis, e "
            "garantindo conformidade legal. Permite dados precisos e integração completa com "
            "Compras & Contratos e Siscont, praticidade com o App Inventário para inventários "
            "descentralizados, relatórios estratégicos, cadastro detalhado e automatizado de bens, "
            "automação contábil, controle de depreciação, gestão de seguros, empréstimos e "
            "manutenções, movimentação simplificada e operações em lote."
        ),
    },
    {
        "id": "sispad-1",
        "section": "Sispad",
        "question": "O que é o Sispad da Implanta e quais são suas funcionalidades?",
        "answer": (
            "O Sispad oferece o controle completo do fluxo de viagens institucionais, gerenciando "
            "solicitações, aprovações, emissão de passagens e prestação de contas com transparência "
            "e praticidade. Inclui gerenciamento integrado de viagens, transparência e conformidade "
            "legal com integração ao Siscont e Portal da Transparência, processo de aprovação "
            "inteligente, perfis personalizados, cálculo automático de despesas, controle de "
            "faturas de passagens e relatórios automatizados."
        ),
    },
    {
        "id": "agenda-financeira-1",
        "section": "Agenda Financeira",
        "question": "O que é a Agenda Financeira da Implanta e quais são seus benefícios?",
        "answer": (
            "É uma solução que permite o acompanhamento detalhado das movimentações financeiras, "
            "registrando receitas, despesas e transferências para tomadas de decisão baseadas em "
            "dados atualizados. Oferece registro detalhado de movimentações financeiras, plano de "
            "contas específico, fluxo de caixa diário e mensal, comparativo mensal por natureza "
            "de despesa, gestão completa de contas a pagar e a receber, integração com o Siscont "
            "e geração de gráficos e relatórios personalizados."
        ),
    },
    {
        "id": "gestao-tcu-1",
        "section": "Gestão TCU",
        "question": "O que é a solução Gestão TCU da Implanta e quais são suas funcionalidades?",
        "answer": (
            "É uma solução que permite a elaboração, organização e envio do Relatório de Gestão, "
            "de acordo com as normas estabelecidas pelo Tribunal de Contas da União (TCU), "
            "facilitando o cumprimento da Lei de Acesso à Informação (LAI). Oferece geração e "
            "envio do Relatório de Gestão, integração com o Portal da Transparência e Siscont, "
            "layout intuitivo e orientações por etapa, recuperação de dados de anos anteriores, "
            "padronização do formato do relatório e fluxo de aprovação entre Conselhos Regionais "
            "e Federal."
        ),
    },
    {
        "id": "portal-transparencia-1",
        "section": "Portal da Transparência",
        "question": "O que é o Portal da Transparência da Implanta e quais são suas funcionalidades?",
        "answer": (
            "É uma solução desenvolvida para garantir total conformidade com a Lei de Acesso à "
            "Informação (LAI), divulgando dados orçamentários, financeiros e administrativos do "
            "Conselho com clareza e acessibilidade. Promove balanços e demonstrativos (financeiro, "
            "patrimonial, orçamentário), comparativos de receita e despesa, relatórios do TCU, "
            "folha de pagamento e quadro de funcionários, diárias, passagens e contratos, consulta "
            "online integrada aos sistemas Implanta.Net e interação direta com o cidadão "
            "(e-SIC e e-OUV)."
        ),
    },
    {
        "id": "siscont-1",
        "section": "Siscont",
        "question": "O que é o Siscont da Implanta e quais são suas funcionalidades?",
        "answer": (
            "O Siscont é uma solução completa que oferece o controle contábil, orçamentário e "
            "financeiro dos Conselhos Profissionais, desenvolvido em conformidade com a legislação "
            "vigente (MCASP e PCASP). Inclui conformidade com a legislação pública, integração e "
            "estratégia para a gestão (propostas orçamentárias, controle de saldos), automação de "
            "processos financeiros (exportação CNAB, controle de tributos, conciliação bancária), "
            "relatórios estratégicos e prestação de contas (balanço patrimonial, DVP, DFC), plano "
            "de contas PCASP, gestão completa da execução orçamentária e gerenciamento de tributos."
        ),
    },
]


# ---------------------------------------------------------------------------
# SQL — cria tabela se não existir
# ---------------------------------------------------------------------------
SQL_CREATE = """
CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS kb_documents;

CREATE TABLE kb_documents (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id    TEXT UNIQUE NOT NULL,
    section     TEXT,
    question    TEXT,
    content     TEXT NOT NULL,
    embedding   vector(1536),
    metadata    JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS kb_documents_embedding_idx
    ON kb_documents USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 10);
"""

SQL_UPSERT = """
INSERT INTO kb_documents (id, chunk_id, section, question, content, embedding, metadata)
VALUES (%s, %s, %s, %s, %s, %s::vector, %s)
ON CONFLICT (chunk_id) DO UPDATE
    SET content   = EXCLUDED.content,
        embedding = EXCLUDED.embedding,
        metadata  = EXCLUDED.metadata;
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_embedding(client: OpenAI, text: str) -> list[float]:
    response = client.embeddings.create(input=text, model=EMBEDDING_MODEL)
    return response.data[0].embedding


def build_content(chunk: dict) -> str:
    """Concatena pergunta + resposta para gerar embedding mais rico."""
    return f"Pergunta: {chunk['question']}\nResposta: {chunk['answer']}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY não definida. Configure no .env ou como variável de ambiente.")

    print(f"🔌 Conectando ao PostgreSQL em {PG_HOST}:{PG_PORT}/{PG_DB}...")
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("📦 Criando extensão e tabela (se não existirem)...")
    cur.execute(SQL_CREATE)

    client = OpenAI(api_key=OPENAI_API_KEY)

    print(f"\n🚀 Inserindo {len(CHUNKS)} chunks...\n")
    for i, chunk in enumerate(CHUNKS, 1):
        content = build_content(chunk)
        print(f"  [{i:02d}/{len(CHUNKS)}] {chunk['section']} — {chunk['question'][:60]}...")

        embedding = get_embedding(client, content)

        metadata = {
            "section": chunk["section"],
            "question": chunk["question"],
            "source": "FAQ_Implanta_Solucoes.pdf",
        }

        cur.execute(
            SQL_UPSERT,
            (
                str(uuid.uuid4()),
                chunk["id"],
                chunk["section"],
                chunk["question"],
                content,
                str(embedding),          # psycopg2 aceita string para vector
                json.dumps(metadata),
            ),
        )

    cur.close()
    conn.close()

    print(f"\n✅ {len(CHUNKS)} chunks inseridos com sucesso!")
    print("   Tabela: kb_documents")
    print("   Índice: ivfflat (cosine)")
    print("\nPróximo passo: configure o N8N para buscar nessa tabela.")


if __name__ == "__main__":
    main()