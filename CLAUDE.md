# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MBA software engineering challenge implementing a **RAG (Retrieval Augmented Generation)** pipeline for PDF document ingestion and semantic Q&A via CLI. Uses **LangChain** with either **Google Generative AI** or **OpenAI** as the LLM/embedding provider, backed by **PostgreSQL + pgvector** for vector storage.

See [docs/DESAFIO.md](docs/DESAFIO.md) for the original challenge specification.

## Setup

```bash
# 1. Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
copy .env.example .env
# Edit .env with your API keys and settings

# 4. Start PostgreSQL with pgvector
docker-compose up -d
```

## Running the Application

```bash
# Ingest a PDF into the vector database
python src/ingest.py

# Start the chat interface
python src/chat.py
```

## Architecture

**Data flow**: PDF → `ingest.py` (chunk + embed → pgvector) → `search.py` (semantic retrieval + RAG prompt) → `chat.py` (LLM chain → user response)

- **[src/ingest.py](src/ingest.py)**: Loads the PDF from `PDF_PATH`, splits it into chunks (**chunk_size=1000**, **overlap=150** — mandatory per DESAFIO), generates embeddings, and stores vectors in the PostgreSQL collection defined by `PG_VECTOR_COLLECTION_NAME`. Uses `pre_delete_collection=True` for idempotent re-runs.
- **[src/search.py](src/search.py)**: Exposes the RAG prompt template (`PROMPT_TEMPLATE`) and a retrieval function that queries the vector store via `similarity_search_with_score(query, k=10)`. Responses are restricted strictly to the retrieved context (no external knowledge).
- **[src/chat.py](src/chat.py)**: Runs the interactive chat loop, calling the search/retrieval chain and printing the LLM response to the user.

## Mandatory Constraints (from DESAFIO)

These values are fixed by the challenge specification — do **not** parameterize or change them without explicit user approval:

| Constraint | Value | Location |
|---|---|---|
| Chunk size | `1000` characters | `src/ingest.py` (`CHUNK_SIZE`) |
| Chunk overlap | `150` characters | `src/ingest.py` (`CHUNK_OVERLAP`) |
| Retrieval `k` | `10` | `src/search.py` (`similarity_search_with_score`) |
| Prompt template | Context-only with negative examples | `src/search.py` (`PROMPT_TEMPLATE`) |
| Refusal message | `"Não tenho informações necessárias para responder sua pergunta."` | `src/search.py` |

## Environment Variables

See [.env.example](.env.example) for all required variables:

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` | LLM provider credentials (configure at least one) |
| `GOOGLE_EMBEDDING_MODEL` | Defaults to `models/embedding-001` |
| `OPENAI_EMBEDDING_MODEL` | Defaults to `text-embedding-3-small` |
| `DATABASE_URL` | PostgreSQL connection string (e.g., `postgresql+psycopg://postgres:postgres@localhost:5432/rag`) |
| `PG_VECTOR_COLLECTION_NAME` | Name of the pgvector collection |
| `PDF_PATH` | Path to the PDF file to ingest |

**Provider selection**: if both `GOOGLE_API_KEY` and `OPENAI_API_KEY` are set, **Google Generative AI** takes precedence (see `_build_embeddings()` in [src/ingest.py](src/ingest.py)).

## Infrastructure

Docker Compose runs two services:
- `postgres_rag`: PostgreSQL 17 on port 5432 with persistent volume
- `bootstrap_vector_ext`: One-shot service that installs the `pgvector` extension on first run

## Git Guardrails

- **NEVER** target `upstream` in any git or `gh` command (push, PR, fetch, etc.)
- All git operations MUST use `origin` (`git@github.com:ratto/mba-ia-desafio-ingestao-busca.git`)
- When creating PRs with `gh pr create`, always pass `--repo ratto/mba-ia-desafio-ingestao-busca` to ensure the fork is targeted, not the upstream org repo

## Required Project Structure (per DESAFIO)

```
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── src/
│   ├── ingest.py
│   ├── search.py
│   └── chat.py
├── document.pdf
└── README.md
```
