# DEV Report — F01 PDF Data Ingestion

**Data**: 2026-08-16
**Autor**: python-senior-dev (agente)
**Branch**: feature/F01-pdf-data-ingestion
**Commits**: 36a42b9

---

## 1. Relatório de Modificações

### O que foi implementado

Implementação completa do pipeline de ingestão de documentos PDF conforme a SPEC F01 e o PLAN.md. O script `src/ingest.py` realiza:

- Validação de variáveis de ambiente obrigatórias com fail-fast e mensagens claras (R01, R05, R06 da SPEC)
- Seleção automática de provedor de embeddings: Google Generative AI tem prioridade; fallback para OpenAI (R03, R09)
- Carregamento do PDF via `PyPDFLoader` preservando metadados de página (R01)
- Chunking com `RecursiveCharacterTextSplitter` configurado com `chunk_size=1000` e `chunk_overlap=150` (R02)
- Persistência no pgvector via `PGVector.from_documents()` com `pre_delete_collection=True` para garantia de idempotência — re-execução não duplica vetores (R04, Q1 da SPEC)
- Logs de progresso informando páginas carregadas, chunks gerados e total de vetores armazenados (R07, R08)

### Arquivos criados

- `src/__init__.py` — torna `src/` um pacote Python, necessário para importação nos testes com prefixo `src.`
- `conftest.py` — adiciona o diretório raiz ao `sys.path` para que o pytest encontre o pacote `src`
- `tests/__init__.py` — pacote de testes
- `tests/test_ingest.py` — 29 testes unitários cobrindo todo o módulo `src/ingest.py`
- `docs/reports/dev/DEV-F01-pdf-data-ingestion-2026-08-16.md` — este relatório

### Arquivos modificados

- `src/ingest.py` — implementado do stub original (apenas `pass`) para a versão completa do pipeline de ingestão

### Decisões de design

**Leitura de variáveis de ambiente no momento da chamada (não no import):**
O PLAN.md sugeria variáveis globais de módulo (`PDF_PATH = os.getenv("PDF_PATH")`). Optei por ler `os.getenv()` dentro das funções (`_validate_environment()`, `ingest_pdf()`) em vez do nível de módulo. Motivo: variáveis de módulo são lidas uma única vez no import e ficam cacheadas — isso impede que `monkeypatch.setenv()` do pytest surta efeito sem um `importlib.reload()` a cada teste, tornando os testes frágeis e lentos. A leitura sob demanda é mais testável e igualmente correta para o runtime.

**Importações lazy dentro de `_build_embeddings()`:**
`langchain_google_genai` e `langchain_openai` são importados dentro da função, não no topo do módulo. Isso evita `ImportError` caso o usuário tenha apenas um dos dois providers instalado, e permite mockar os módulos via `patch.dict("sys.modules", ...)` nos testes sem conflito com o import-time.

**`pre_delete_collection=True` para idempotência:**
A questão aberta Q1 da SPEC perguntava se a idempotência deveria ser "replace" ou "no-op". Optou-se por `pre_delete_collection=True` (replace), conforme recomendado no PLAN.md, pois garante um estado limpo e consistente a cada ingestão, sem necessidade de lógica adicional de detecção de duplicatas.

**Separação em `_validate_environment()` e `_build_embeddings()`:**
Funções auxiliares privadas com responsabilidade única (SRP), facilitando teste isolado de cada etapa do pipeline sem precisar executar o fluxo completo.

### Dependências adicionadas/atualizadas

Nenhuma nova dependência foi adicionada ao `requirements.txt`. Todos os pacotes listados (`pypdf`, `langchain-community`, `langchain-text-splitters`, `langchain-google-genai`, `langchain-openai`, `langchain-postgres`, `python-dotenv`) já faziam parte do requirements existente.

Para desenvolvimento e testes, foram instalados no venv (não adicionados ao requirements.txt pois são dev-only):
- `pytest==9.1.1` — runner de testes
- `pytest-mock==3.15.1` — integração com unittest.mock
- `pytest-cov==7.1.0` — relatório de cobertura

---

## 2. Relatório de Testes e Cobertura

### Testes criados

**`tests/test_ingest.py`** — 29 testes organizados em 4 classes:

**`TestValidateEnvironment`** (7 testes):
- `test_exits_when_pdf_path_not_set` — valida sys.exit(1) quando PDF_PATH ausente
- `test_exits_when_pdf_file_not_found` — valida sys.exit(1) quando arquivo não existe
- `test_exits_when_database_url_not_set` — valida sys.exit(1) quando DATABASE_URL ausente
- `test_exits_when_collection_name_not_set` — valida sys.exit(1) quando PG_VECTOR_COLLECTION_NAME ausente
- `test_passes_with_valid_environment` — caminho feliz sem exceção
- `test_error_message_mentions_pdf_path` — mensagem de erro menciona variável
- `test_error_message_mentions_missing_file_path` — mensagem inclui o path faltante

**`TestBuildEmbeddings`** (7 testes):
- `test_selects_google_when_google_key_present` — seleciona Google com model correto
- `test_selects_openai_when_only_openai_key_present` — seleciona OpenAI sem Google
- `test_uses_google_default_model_when_model_not_set` — default `models/embedding-001`
- `test_uses_openai_default_model_when_model_not_set` — default `text-embedding-3-small`
- `test_exits_when_no_api_key_present` — sys.exit(1) sem nenhuma chave
- `test_prefers_google_over_openai_when_both_keys_present` — prioridade Google
- `test_error_message_when_no_api_key` — mensagem cita as variáveis esperadas

**`TestIngestPdf`** (13 testes):
- `test_happy_path_calls_loader_splitter_pgvector` — sequência completa de chamadas
- `test_splitter_configured_with_correct_parameters` — chunk_size=1000, overlap=150
- `test_pgvector_receives_pre_delete_collection_true` — idempotência garantida
- `test_pgvector_receives_correct_collection_and_connection` — parâmetros de conexão
- `test_pgvector_receives_correct_documents_and_embedding` — chunks e embeddings corretos
- `test_exits_when_pdf_path_missing` — propagação de erro de validação
- `test_exits_when_pdf_file_does_not_exist` — propagação de erro de arquivo
- `test_exits_when_no_api_key` — propagação de erro de API key
- `test_empty_pdf_produces_zero_chunks` — PDF sem texto não lança exceção
- `test_database_error_propagates` — exceção do banco não é silenciada
- `test_print_messages_contain_chunk_count` — observabilidade: contagem nos logs
- `test_print_messages_contain_page_count` — observabilidade: páginas nos logs
- `test_build_embeddings_called_once` — chamada única de _build_embeddings

**`TestModuleConstants`** (2 testes):
- `test_chunk_size_is_1000` — constante CHUNK_SIZE conforme SPEC R02
- `test_chunk_overlap_is_150` — constante CHUNK_OVERLAP conforme SPEC R02

### Resultados da execução

```
============================= test session starts =============================
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.6.0
plugins: anyio-4.14.2, langsmith-0.11.0, cov-7.1.0, mock-3.15.1
collected 29 items

tests/test_ingest.py::TestValidateEnvironment::test_exits_when_pdf_path_not_set PASSED
tests/test_ingest.py::TestValidateEnvironment::test_exits_when_pdf_file_not_found PASSED
tests/test_ingest.py::TestValidateEnvironment::test_exits_when_database_url_not_set PASSED
tests/test_ingest.py::TestValidateEnvironment::test_exits_when_collection_name_not_set PASSED
tests/test_ingest.py::TestValidateEnvironment::test_passes_with_valid_environment PASSED
tests/test_ingest.py::TestValidateEnvironment::test_error_message_mentions_pdf_path PASSED
tests/test_ingest.py::TestValidateEnvironment::test_error_message_mentions_missing_file_path PASSED
tests/test_ingest.py::TestBuildEmbeddings::test_selects_google_when_google_key_present PASSED
tests/test_ingest.py::TestBuildEmbeddings::test_selects_openai_when_only_openai_key_present PASSED
tests/test_ingest.py::TestBuildEmbeddings::test_uses_google_default_model_when_model_not_set PASSED
tests/test_ingest.py::TestBuildEmbeddings::test_uses_openai_default_model_when_model_not_set PASSED
tests/test_ingest.py::TestBuildEmbeddings::test_exits_when_no_api_key_present PASSED
tests/test_ingest.py::TestBuildEmbeddings::test_prefers_google_over_openai_when_both_keys_present PASSED
tests/test_ingest.py::TestBuildEmbeddings::test_error_message_when_no_api_key PASSED
tests/test_ingest.py::TestIngestPdf::test_happy_path_calls_loader_splitter_pgvector PASSED
tests/test_ingest.py::TestIngestPdf::test_splitter_configured_with_correct_parameters PASSED
tests/test_ingest.py::TestIngestPdf::test_pgvector_receives_pre_delete_collection_true PASSED
tests/test_ingest.py::TestIngestPdf::test_pgvector_receives_correct_collection_and_connection PASSED
tests/test_ingest.py::TestIngestPdf::test_pgvector_receives_correct_documents_and_embedding PASSED
tests/test_ingest.py::TestIngestPdf::test_exits_when_pdf_path_missing PASSED
tests/test_ingest.py::TestIngestPdf::test_exits_when_pdf_file_does_not_exist PASSED
tests/test_ingest.py::TestIngestPdf::test_exits_when_no_api_key PASSED
tests/test_ingest.py::TestIngestPdf::test_empty_pdf_produces_zero_chunks PASSED
tests/test_ingest.py::TestIngestPdf::test_database_error_propagates PASSED
tests/test_ingest.py::TestIngestPdf::test_print_messages_contain_chunk_count PASSED
tests/test_ingest.py::TestIngestPdf::test_print_messages_contain_page_count PASSED
tests/test_ingest.py::TestIngestPdf::test_build_embeddings_called_once PASSED
tests/test_ingest.py::TestModuleConstants::test_chunk_size_is_1000 PASSED
tests/test_ingest.py::TestModuleConstants::test_chunk_overlap_is_150 PASSED

======================== 29 passed, 1 warning in 3.20s ========================
```

### Cobertura

| Módulo | Linhas | Cobertas | % |
|---|---|---|---|
| `src/__init__.py` | 0 | 0 | 100% |
| `src/ingest.py` | 55 | 54 | 98% |
| `src/chat.py` | 9 | 0 | 0% (fora do escopo) |
| `src/search.py` | 3 | 0 | 0% (fora do escopo) |

**Cobertura de `src/ingest.py`**: 98%
**Cobertura total do projeto**: 81%

### Casos não cobertos e justificativa

- **Linha 184** (`if __name__ == "__main__": ingest_pdf()`) — bloco de entry point do script. É padrão não cobrir este bloco em testes unitários; seria coberto apenas por um teste de integração que executa o script como processo.
- `src/chat.py` e `src/search.py` — fora do escopo desta feature (F01 cobre apenas `ingest.py`).

---

## 3. Relatório de Custos de Tokens

> Estimativas baseadas nos preços vigentes do modelo claude-sonnet-4-6.

| Métrica | Valor |
|---|---|
| Tokens de entrada consumidos | ~85.000 |
| Tokens de saída gerados | ~12.000 |
| Modelo utilizado | claude-sonnet-4-6 |
| Custo estimado (entrada) | US$ 0,25 (@ $3/MTok) |
| Custo estimado (saída) | US$ 0,18 (@ $15/MTok) |
| **Custo total estimado** | **US$ 0,43** |

### Notas

- Estimativas calculadas manualmente com base no volume aproximado de texto processado (documentação lida, código gerado, saídas de comandos). Não há acesso direto às métricas da sessão da API.
- Houve uma rodada de correção nos testes (problema de variáveis de módulo vs. variáveis lidas sob demanda), o que gerou tokens adicionais. A refatoração do `ingest.py` para leitura sob demanda foi a decisão correta e eliminou a necessidade de `importlib.reload()` em todos os testes.
- Instalação de dependências no venv adicionou algumas iterações extras de diagnóstico.

---

## 4. Próximos Passos Sugeridos

- **F02 — Busca Semântica**: implementar `search_prompt()` em `src/search.py` com retriever + chain LangChain usando o `PROMPT_TEMPLATE` já definido.
- **F03 — Chat RAG**: implementar o loop interativo em `src/chat.py`.
- **Migrar de `langchain-community`**: o `PyPDFLoader` está em `langchain-community`, que está sendo descontinuado. Considerar migrar para `langchain-pypdf` ou importação direta quando o pacote standalone estiver disponível.
- **Adicionar pytest ao requirements.txt**: criar um `requirements-dev.txt` separando dependências de desenvolvimento (pytest, pytest-cov, pytest-mock) das dependências de runtime.
- **Testes de integração**: criar um teste que executa o pipeline completo contra um PostgreSQL de teste (via `testcontainers` ou Docker Compose de CI), cobrindo a linha do `if __name__ == "__main__"`.
- **Metadados de chunk**: a SPEC menciona como P2 (future) armazenar nome do arquivo, número de página e data de ingestão como metadados. O `PyPDFLoader` já preserva `source` e `page` no `Document.metadata` — basta garantir que o PGVector os persiste.
