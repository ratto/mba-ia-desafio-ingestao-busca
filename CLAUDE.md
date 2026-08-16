# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MBA software engineering challenge implementing a RAG (Retrieval Augmented Generation) pipeline for PDF document ingestion and semantic Q&A. Uses LangChain with either Google Generative AI or OpenAI as the LLM/embedding provider, backed by PostgreSQL + pgvector for vector storage.

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

- **[src/ingest.py](src/ingest.py)**: Loads the PDF from `PDF_PATH`, splits it into chunks, generates embeddings, and stores vectors in the PostgreSQL collection defined by `PG_VECTOR_COLLECTION_NAME`.
- **[src/search.py](src/search.py)**: Builds the RAG prompt template and exposes a retrieval function that queries the vector store for relevant context. Responses are restricted strictly to the retrieved context (no external knowledge).
- **[src/chat.py](src/chat.py)**: Runs the interactive chat loop, calling the search/retrieval chain and streaming LLM responses to the user.

## Environment Variables

See [.env.example](.env.example) for all required variables:

| Variable | Description |
|---|---|
| `GOOGLE_API_KEY` / `OPENAI_API_KEY` | LLM provider credentials (configure one or both) |
| `GOOGLE_EMBEDDING_MODEL` | Defaults to `models/embedding-001` |
| `OPENAI_EMBEDDING_MODEL` | Defaults to `text-embedding-3-small` |
| `DATABASE_URL` | PostgreSQL connection string |
| `PG_VECTOR_COLLECTION_NAME` | Name of the pgvector collection |
| `PDF_PATH` | Path to the PDF file to ingest |

## Infrastructure

Docker Compose runs two services:
- `postgres_rag`: PostgreSQL 17 on port 5432 with persistent volume
- `bootstrap_vector_ext`: One-shot service that installs the `pgvector` extension on first run
