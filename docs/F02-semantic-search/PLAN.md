# F02 — Semantic Search: Implementation Plan

## Overview

Implement `search_prompt()` in `src/search.py` to build a LangChain RAG chain that retrieves the top-10 most semantically similar chunks from pgvector and generates a context-only response using the `PROMPT_TEMPLATE` already defined in the file.

**Entry point**: called by `src/chat.py` as `chain = search_prompt()`  
**Key file**: [src/search.py](../../src/search.py)

---

## Dependencies (already in requirements.txt)

| Package | Purpose |
|---|---|
| `langchain-postgres` | `PGVector` — vector store and retriever |
| `langchain-google-genai` | `GoogleGenerativeAIEmbeddings`, `ChatGoogleGenerativeAI` |
| `langchain-openai` | `OpenAIEmbeddings`, `ChatOpenAI` |
| `langchain-core` | `PromptTemplate`, LCEL pipe (`\|`) |
| `python-dotenv` | `.env` loading |
| `psycopg` / `psycopg-binary` | PostgreSQL driver used by `PGVector` |

No new packages required.

---

## Environment Variables

All read from `.env` via `load_dotenv()`:

```
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag
PG_VECTOR_COLLECTION_NAME=rag_docs

# One or both — Google takes priority if both are set
GOOGLE_API_KEY=...
GOOGLE_EMBEDDING_MODEL=models/embedding-001
GOOGLE_LLM_MODEL=gemini-1.5-flash

OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_LLM_MODEL=gpt-4o-mini
```

---

## Implementation Steps

### Step 1 — Add imports and load environment

```python
import os
import sys
from dotenv import load_dotenv
from langchain_postgres import PGVector
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

load_dotenv()
```

### Step 2 — Build embeddings provider (same logic as F01)

The embedding model must match the one used during ingest — otherwise similarity search returns garbage.

```python
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
    return None
```

### Step 3 — Build LLM provider

```python
def _build_llm():
    if os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash")
        return ChatGoogleGenerativeAI(model=model)
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        model = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        return ChatOpenAI(model=model)
    print("Erro: nenhuma chave de API configurada (GOOGLE_API_KEY ou OPENAI_API_KEY).")
    return None
```

### Step 4 — Implement `search_prompt()`

```python
def search_prompt(question=None):
    database_url = os.getenv("DATABASE_URL")
    collection_name = os.getenv("PG_VECTOR_COLLECTION_NAME")

    if not database_url:
        print("Erro: variável de ambiente DATABASE_URL não definida.")
        return None
    if not collection_name:
        print("Erro: variável de ambiente PG_VECTOR_COLLECTION_NAME não definida.")
        return None

    embeddings = _build_embeddings()
    if embeddings is None:
        return None

    llm = _build_llm()
    if llm is None:
        return None

    try:
        vector_store = PGVector(
            embeddings=embeddings,
            collection_name=collection_name,
            connection=database_url,
        )
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

    retriever = vector_store.as_retriever(search_kwargs={"k": 10})

    prompt = PromptTemplate(
        input_variables=["contexto", "pergunta"],
        template=PROMPT_TEMPLATE,
    )

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    chain = (
        {"contexto": retriever | format_docs, "pergunta": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    print("Chain RAG inicializada com sucesso.")
    return chain
```

> **Note on LCEL**: o operador `|` (pipe) é o padrão moderno do LangChain (LCEL). A chain acima: (1) recebe a pergunta do usuário, (2) usa o `retriever` para buscar os 10 chunks mais similares, (3) formata os chunks como string e os injeta em `{contexto}`, (4) passa a pergunta original em `{pergunta}`, (5) envia o prompt ao LLM, (6) parseia a saída como string.

> **Note on embeddings**: o modelo de embedding passado ao `PGVector` **deve ser o mesmo** usado na ingestão (F01), caso contrário as dimensões do vetor não coincidem e a busca falha. A lógica de seleção de provedor é idêntica à de `_build_embeddings()` em `ingest.py`.

---

## Final `src/search.py`

```python
import os
import sys
from dotenv import load_dotenv
from langchain_postgres import PGVector
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

load_dotenv()

PROMPT_TEMPLATE = """
CONTEXTO:
{contexto}

REGRAS:
- Responda somente com base no CONTEXTO.
- Se a informação não estiver explicitamente no CONTEXTO, responda:
  "Não tenho informações necessárias para responder sua pergunta."
- Nunca invente ou use conhecimento externo.
- Nunca produza opiniões ou interpretações além do que está escrito.

EXEMPLOS DE PERGUNTAS FORA DO CONTEXTO:
Pergunta: "Qual é a capital da França?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Quantos clientes temos em 2024?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Você acha isso bom ou ruim?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

PERGUNTA DO USUÁRIO:
{pergunta}

RESPONDA A "PERGUNTA DO USUÁRIO"
"""


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
    return None


def _build_llm():
    if os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash")
        return ChatGoogleGenerativeAI(model=model)
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        model = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        return ChatOpenAI(model=model)
    print("Erro: nenhuma chave de API configurada (GOOGLE_API_KEY ou OPENAI_API_KEY).")
    return None


def search_prompt(question=None):
    database_url = os.getenv("DATABASE_URL")
    collection_name = os.getenv("PG_VECTOR_COLLECTION_NAME")

    if not database_url:
        print("Erro: variável de ambiente DATABASE_URL não definida.")
        return None
    if not collection_name:
        print("Erro: variável de ambiente PG_VECTOR_COLLECTION_NAME não definida.")
        return None

    embeddings = _build_embeddings()
    if embeddings is None:
        return None

    llm = _build_llm()
    if llm is None:
        return None

    try:
        vector_store = PGVector(
            embeddings=embeddings,
            collection_name=collection_name,
            connection=database_url,
        )
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

    retriever = vector_store.as_retriever(search_kwargs={"k": 10})

    prompt = PromptTemplate(
        input_variables=["contexto", "pergunta"],
        template=PROMPT_TEMPLATE,
    )

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    chain = (
        {"contexto": retriever | format_docs, "pergunta": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    print("Chain RAG inicializada com sucesso.")
    return chain
```

---

## Execution Flow

```
search_prompt()
        │
        ├─ [validate] DATABASE_URL e PG_VECTOR_COLLECTION_NAME existem?
        │         └─ NÃO → print erro + return None
        │
        ├─ [embed]   GOOGLE_API_KEY presente? → GoogleGenerativeAIEmbeddings
        │            else OPENAI_API_KEY?     → OpenAIEmbeddings
        │            else                     → print erro + return None
        │
        ├─ [llm]     GOOGLE_API_KEY presente? → ChatGoogleGenerativeAI
        │            else OPENAI_API_KEY?     → ChatOpenAI
        │            else                     → print erro + return None
        │
        ├─ [connect] PGVector(embeddings, collection_name, connection)
        │         └─ exceção → print erro + return None
        │
        ├─ [retriever] vector_store.as_retriever(k=10)
        │
        └─ [chain]   {contexto: retriever | format_docs, pergunta: passthrough}
                     | PromptTemplate(PROMPT_TEMPLATE)
                     | LLM
                     | StrOutputParser()
                     └─ return chain
```

---

## Testing Checklist

- [ ] `search_prompt()` retorna chain funcional com `.env` correto e banco acessível
- [ ] `chain.invoke("pergunta sobre o PDF")` retorna string com resposta baseada no contexto
- [ ] `chain.invoke("pergunta fora do escopo")` retorna `"Não tenho informações necessárias para responder sua pergunta."`
- [ ] `DATABASE_URL` não definido: imprime erro e retorna `None`
- [ ] `PG_VECTOR_COLLECTION_NAME` não definido: imprime erro e retorna `None`
- [ ] Sem chave de API: imprime erro e retorna `None`
- [ ] Banco inacessível: imprime erro com detalhes e retorna `None`
- [ ] Provider Google selecionado quando `GOOGLE_API_KEY` presente
- [ ] Provider OpenAI selecionado quando apenas `OPENAI_API_KEY` presente
- [ ] Verificação manual end-to-end:
  ```bash
  python -c "
  from src.search import search_prompt
  chain = search_prompt()
  if chain:
      print(chain.invoke('Qual o tema principal do documento?'))
  "
  ```
