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
├── conftest.py          # Configuração do pytest (sys.path)
├── .env.example
├── src/
│   ├── __init__.py
│   ├── ingest.py        # Ingestão do PDF no pgVector
│   ├── search.py        # Chain RAG LCEL (retriever + prompt + LLM)
│   └── chat.py          # CLI interativa de perguntas
├── tests/
│   ├── __init__.py
│   ├── test_ingest.py   # 29 testes unitários para ingest.py
│   ├── test_search.py   # 47 testes unitários para search.py
│   └── test_chat.py     # 27 testes unitários para chat.py
├── document.pdf         # PDF a ser ingerido
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
| `OPENAI_LLM_MODEL`          | Modelo LLM OpenAI (padrão: `gpt-5.6-luna`)                      |
| `GOOGLE_API_KEY`            | Chave do Google Generative AI (alternativa à OpenAI)             |
| `GOOGLE_EMBEDDING_MODEL`    | Modelo de embedding Google (padrão: `models/embedding-001`)      |
| `GOOGLE_LLM_MODEL`          | Modelo LLM Google (padrão: `gemini-3.0-flash`)                   |
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
Chat RAG iniciado. Digite sua pergunta ou 'sair' para encerrar.

Você: Qual o faturamento da Empresa SuperTechIABrazil?
Assistente: O faturamento foi de 10 milhões de reais.

Você: Quantos clientes temos em 2024?
Assistente: Não tenho informações necessárias para responder sua pergunta.

Você: sair
Encerrando o chat. Até logo!
```

O chat:

1. Inicializa a chain RAG via `search_prompt()` (fail-fast em caso de erro de configuração)
2. Vetoriza a pergunta
3. Recupera os **10 chunks mais relevantes** (`k=10`) via `similarity_search_with_score`
4. Monta o prompt e chama a LLM via chain LCEL
5. Retorna a resposta ao usuário

---

## Regras do Prompt

O sistema responde **exclusivamente com base no conteúdo do PDF**. Perguntas fora do contexto retornam:

> "Não tenho informações necessárias para responder sua pergunta."

Nenhum conhecimento externo, opinião ou interpretação além do que está escrito no documento é permitido.

---

## Testes

```bash
pip install pytest pytest-cov pytest-mock
pytest --cov=src tests/
```

---

## Documentação

- [docs/PRD.md](docs/PRD.md) — Product Requirements Document
- [CLAUDE.md](CLAUDE.md) — guia para desenvolvimento assistido por IA

---

## Resultados do Projeto

### Cobertura de Testes

| Módulo           | Testes | Linhas | Cobertas | Cobertura |
| ---------------- | ------:| ------:| --------:| ---------:|
| `src/ingest.py`  | 29     | 55     | 54       | 98%       |
| `src/search.py`  | 47     | 58     | 58       | 100%      |
| `src/chat.py`    | 27     | 37     | 36       | 97%       |
| **Total**        | **103**| **150**| **148**  | **99%**   |

Todos os **103 testes passaram** sem falhas.

```
============================= test session starts ==============================
platform linux -- Python 3.10.12, pytest-9.1.1, pluggy-1.6.0
collected 103 items

tests/test_chat.py    27 passed
tests/test_ingest.py  29 passed
tests/test_search.py  47 passed

======================== 103 passed, 1 warning in 1.47s ========================
```

### Consumo de Tokens (claude-sonnet-4-6)

> Estimativas baseadas no volume de texto processado e gerado por sessão. Preços de referência: US$ 3/MTok (entrada) e US$ 15/MTok (saída).

| Feature                      | Tokens entrada | Tokens saída | Custo estimado |
| ---------------------------- | -------------: | -----------: | -------------: |
| F01 — Ingestão de PDF        | ~85.000        | ~12.000      | US$ 0,43       |
| F02 — Busca Semântica        | ~35.000        | ~8.000       | US$ 0,225      |
| F03 — Chat Interativo        | ~28.000        | ~7.500       | US$ 0,197      |
| **Total**                    | **~148.000**   | **~27.500**  | **US$ 0,852**  |
