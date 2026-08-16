# F01 — PDF Data Ingestion: Implementation Plan

## Overview

Implement `src/ingest.py` to load a PDF, split it into chunks, generate embeddings, and store vectors in PostgreSQL with pgvector. All logic lives inside `ingest_pdf()` which is already scaffolded.

**Entry point**: `python src/ingest.py`  
**Key file**: [src/ingest.py](../../src/ingest.py)

---

## Dependencies (already in requirements.txt)

| Package | Purpose |
|---|---|
| `pypdf` | PDF text extraction (used internally by LangChain's PyPDFLoader) |
| `langchain-community` | `PyPDFLoader` |
| `langchain-text-splitters` | `RecursiveCharacterTextSplitter` |
| `langchain-google-genai` | `GoogleGenerativeAIEmbeddings` |
| `langchain-openai` | `OpenAIEmbeddings` |
| `langchain-postgres` | `PGVector` |
| `python-dotenv` | `.env` loading |
| `psycopg` / `psycopg-binary` | PostgreSQL async driver used by `PGVector` |

No new packages required.

---

## Environment Variables

All read from `.env` via `load_dotenv()`:

```
PDF_PATH=./data/document.pdf
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag
PG_VECTOR_COLLECTION_NAME=rag_docs

# One or both — Google takes priority if both are set
GOOGLE_API_KEY=...
GOOGLE_EMBEDDING_MODEL=models/embedding-001

OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
```

---

## Implementation Steps

### Step 1 — Validate environment and file

Before any I/O, check that `PDF_PATH` is set and the file exists. Fail fast with a clear message.

```python
import os
import sys
from dotenv import load_dotenv

load_dotenv()

PDF_PATH = os.getenv("PDF_PATH")
DATABASE_URL = os.getenv("DATABASE_URL")
PG_VECTOR_COLLECTION_NAME = os.getenv("PG_VECTOR_COLLECTION_NAME")

def ingest_pdf():
    if not PDF_PATH:
        print("Erro: variável de ambiente PDF_PATH não definida.")
        sys.exit(1)
    if not os.path.exists(PDF_PATH):
        print(f"Erro: arquivo não encontrado: {PDF_PATH}")
        sys.exit(1)
    if not DATABASE_URL:
        print("Erro: variável de ambiente DATABASE_URL não definida.")
        sys.exit(1)
    if not PG_VECTOR_COLLECTION_NAME:
        print("Erro: variável de ambiente PG_VECTOR_COLLECTION_NAME não definida.")
        sys.exit(1)
```

### Step 2 — Select embedding provider

Prefer Google if `GOOGLE_API_KEY` is present; fall back to OpenAI.

```python
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings

def _build_embeddings():
    if os.getenv("GOOGLE_API_KEY"):
        model = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/embedding-001")
        return GoogleGenerativeAIEmbeddings(model=model)
    if os.getenv("OPENAI_API_KEY"):
        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        return OpenAIEmbeddings(model=model)
    print("Erro: nenhuma chave de API configurada (GOOGLE_API_KEY ou OPENAI_API_KEY).")
    sys.exit(1)
```

### Step 3 — Load PDF

Use `PyPDFLoader` which splits by page and preserves page metadata.

```python
from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader(PDF_PATH)
pages = loader.load()
print(f"{len(pages)} página(s) carregada(s) de '{PDF_PATH}'")
```

### Step 4 — Split into chunks

Use `RecursiveCharacterTextSplitter` with the required parameters.

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=150,
)
chunks = splitter.split_documents(pages)
print(f"{len(chunks)} chunk(s) gerado(s)")
```

`RecursiveCharacterTextSplitter` tries to split on `\n\n`, `\n`, ` `, `""` in order, which produces more semantically coherent chunks than splitting on a fixed character alone.

### Step 5 — Store vectors in pgvector

`PGVector.from_documents()` creates the collection if it does not exist, embeds all chunks, and inserts them in batch.

```python
from langchain_postgres import PGVector

vector_store = PGVector.from_documents(
    documents=chunks,
    embedding=embeddings,
    collection_name=PG_VECTOR_COLLECTION_NAME,
    connection=DATABASE_URL,
)
print(f"Ingestão concluída: {len(chunks)} vetores armazenados em '{PG_VECTOR_COLLECTION_NAME}'")
```

> **Note on idempotency**: `PGVector.from_documents()` appends by default. To replace the collection on each run, pass `pre_delete_collection=True`. The recommended default for this project is `pre_delete_collection=True` so re-ingesting a PDF always produces a clean, consistent state.

---

## Final `src/ingest.py`

```python
import os
import sys
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_postgres import PGVector

load_dotenv()

PDF_PATH = os.getenv("PDF_PATH")
DATABASE_URL = os.getenv("DATABASE_URL")
PG_VECTOR_COLLECTION_NAME = os.getenv("PG_VECTOR_COLLECTION_NAME")


def _build_embeddings():
    if os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        model = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/embedding-001")
        return GoogleGenerativeAIEmbeddings(model=model)
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import OpenAIEmbeddings
        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        return OpenAIEmbeddings(model=model)
    print("Erro: nenhuma chave de API configurada (GOOGLE_API_KEY ou OPENAI_API_KEY).")
    sys.exit(1)


def ingest_pdf():
    if not PDF_PATH:
        print("Erro: variável de ambiente PDF_PATH não definida.")
        sys.exit(1)
    if not os.path.exists(PDF_PATH):
        print(f"Erro: arquivo não encontrado: {PDF_PATH}")
        sys.exit(1)
    if not DATABASE_URL:
        print("Erro: variável de ambiente DATABASE_URL não definida.")
        sys.exit(1)
    if not PG_VECTOR_COLLECTION_NAME:
        print("Erro: variável de ambiente PG_VECTOR_COLLECTION_NAME não definida.")
        sys.exit(1)

    embeddings = _build_embeddings()

    loader = PyPDFLoader(PDF_PATH)
    pages = loader.load()
    print(f"{len(pages)} página(s) carregada(s) de '{PDF_PATH}'")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
    )
    chunks = splitter.split_documents(pages)
    print(f"{len(chunks)} chunk(s) gerado(s)")

    PGVector.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=PG_VECTOR_COLLECTION_NAME,
        connection=DATABASE_URL,
        pre_delete_collection=True,
    )
    print(f"Ingestão concluída: {len(chunks)} vetores armazenados em '{PG_VECTOR_COLLECTION_NAME}'")


if __name__ == "__main__":
    ingest_pdf()
```

---

## Execution Flow

```
python src/ingest.py
        │
        ├─ [validate] PDF_PATH, DATABASE_URL, PG_VECTOR_COLLECTION_NAME existem?
        │         └─ NÃO → print erro + sys.exit(1)
        │
        ├─ [embed]   GOOGLE_API_KEY presente? → GoogleGenerativeAIEmbeddings
        │            else OPENAI_API_KEY?     → OpenAIEmbeddings
        │            else                     → print erro + sys.exit(1)
        │
        ├─ [load]    PyPDFLoader(PDF_PATH).load()  → List[Document] (por página)
        │
        ├─ [split]   RecursiveCharacterTextSplitter(1000, 150).split_documents()
        │
        └─ [store]   PGVector.from_documents(pre_delete_collection=True)
                     └─ cria/recria a coleção + insere vetores em batch
```

---

## Testing Checklist

- [ ] PDF válido: script termina com código 0 e imprime contagem de chunks
- [ ] `PDF_PATH` não definido: imprime `"Erro: variável de ambiente PDF_PATH não definida."` e sai com código 1
- [ ] Arquivo inexistente: imprime erro com o path e sai com código 1
- [ ] Sem chave de API: imprime erro e sai com código 1
- [ ] Banco inacessível: exception do psycopg propagada com traceback legível
- [ ] Re-execução com mesmo PDF: contagem de vetores no banco permanece igual (idempotência via `pre_delete_collection=True`)
- [ ] Verificação direta no banco:
  ```sql
  SELECT count(*) FROM langchain_pg_embedding
  JOIN langchain_pg_collection ON langchain_pg_collection.uuid = langchain_pg_embedding.collection_id
  WHERE langchain_pg_collection.name = '<PG_VECTOR_COLLECTION_NAME>';
  ```
