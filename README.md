# Desafio MBA Engenharia de Software com IA — Full Cycle

Pipeline RAG (Retrieval-Augmented Generation) para ingestão de documentos PDF e busca semântica via CLI, usando **LangChain**, **PostgreSQL + pgVector** e **OpenAI** ou **Google Generative AI**.

---

## Requisitos

- Python 3.10+
- Docker e Docker Compose
- Chave de API de um dos provedores: **OpenAI** (`OPENAI_API_KEY`) ou **Google Generative AI** (`GOOGLE_API_KEY`)

---

## Estrutura do Projeto

```
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── src/
│   ├── ingest.py    # Ingestão do PDF no pgVector
│   ├── search.py    # Busca semântica + prompt RAG
│   └── chat.py      # CLI interativa de perguntas
├── document.pdf     # PDF a ser ingerido
└── README.md
```

---

## Setup

### 1. Clone e crie o ambiente virtual

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Configure as variáveis de ambiente

```bash
# Windows
copy .env.example .env
# Linux/macOS
cp .env.example .env
```

Edite o arquivo `.env` e preencha:

| Variável                    | Descrição                                                        |
| --------------------------- | ---------------------------------------------------------------- |
| `OPENAI_API_KEY`            | Chave da OpenAI (obrigatória se usar OpenAI)                     |
| `OPENAI_EMBEDDING_MODEL`    | Modelo de embedding OpenAI (padrão: `text-embedding-3-small`)    |
| `GOOGLE_API_KEY`            | Chave do Google Generative AI (alternativa à OpenAI)             |
| `GOOGLE_EMBEDDING_MODEL`    | Modelo de embedding Google (padrão: `models/embedding-001`)      |
| `DATABASE_URL`              | Ex.: `postgresql+psycopg://postgres:postgres@localhost:5432/rag` |
| `PG_VECTOR_COLLECTION_NAME` | Nome da coleção pgvector (ex.: `documents`)                      |
| `PDF_PATH`                  | Caminho para o PDF (ex.: `document.pdf`)                         |

> **Nota**: se ambas as chaves (`GOOGLE_API_KEY` e `OPENAI_API_KEY`) estiverem definidas, o sistema prioriza **Google Generative AI**.

### 4. Suba o PostgreSQL com pgVector

```bash
docker-compose up -d
```

Isso inicia dois serviços:

- `postgres_rag`: PostgreSQL 17 na porta 5432
- `bootstrap_vector_ext`: instala a extensão `vector` automaticamente

---

## Executando a Aplicação

### 1. Ingestão do PDF

```bash
python src/ingest.py
```

O script:

1. Carrega o PDF definido em `PDF_PATH`
2. Divide o conteúdo em chunks de **1000 caracteres** com **overlap de 150**
3. Gera embeddings via provedor configurado
4. Persiste os vetores na coleção `PG_VECTOR_COLLECTION_NAME` (re-executar limpa e reingere — idempotente)

### 2. Chat interativo (busca semântica)

```bash
python src/chat.py
```

Exemplo de interação:

```
Faça sua pergunta:

PERGUNTA: Qual o faturamento da Empresa SuperTechIABrazil?
RESPOSTA: O faturamento foi de 10 milhões de reais.

---

PERGUNTA: Quantos clientes temos em 2024?
RESPOSTA: Não tenho informações necessárias para responder sua pergunta.
```

O chat:

1. Vetoriza a pergunta
2. Recupera os **10 chunks mais relevantes** (`k=10`) via `similarity_search_with_score`
3. Monta o prompt e chama a LLM
4. Retorna a resposta ao usuário

---

## Regras do Prompt

O sistema responde **exclusivamente com base no conteúdo do PDF**. Perguntas fora do contexto retornam:

> "Não tenho informações necessárias para responder sua pergunta."

Nenhum conhecimento externo, opinião ou interpretação além do que está escrito no documento é permitido.

---

## Documentação

- [docs/PRD.md](docs/PRD.md) — Product Requirements Document
- [CLAUDE.md](CLAUDE.md) — guia para desenvolvimento assistido por IA
