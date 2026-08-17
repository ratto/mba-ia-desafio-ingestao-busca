# DEV Report — F02 Semantic Search

**Data**: 2026-08-16
**Autor**: python-senior-dev (agente)
**Branch**: feature/F02-semantic-search
**Commits**: `14a48d1`

---

## 1. Relatório de Modificações

### O que foi implementado

Substituição do stub `search_prompt()` em `src/search.py` por uma implementação completa da chain RAG usando LangChain LCEL. A função agora:

- Valida as variáveis de ambiente `DATABASE_URL` e `PG_VECTOR_COLLECTION_NAME` antes de qualquer I/O (fail-fast)
- Constrói o provedor de embeddings via `_build_embeddings()` (Google com prioridade, fallback OpenAI)
- Constrói o provedor de LLM via `_build_llm()` (Google com prioridade, fallback OpenAI)
- Instancia `PGVector` para conexão ao banco de dados com os vetores ingeridos pela F01
- Cria um retriever com `k=10` fixo (requisito obrigatório do DESAFIO)
- Monta uma chain LCEL com `PromptTemplate(PROMPT_TEMPLATE)`, LLM e `StrOutputParser`
- Retorna a chain invocável ao chamador (`chat.py`), ou `None` em caso de erro
- Imprime mensagem de confirmação indicando provedor e `k=10` após inicialização bem-sucedida

### Arquivos criados

- `tests/test_search.py` — 46 testes unitários cobrindo todas as funções públicas e privadas de `src/search.py`

### Arquivos modificados

- `src/search.py` — implementação completa substituindo o stub `pass`. Adicionadas as funções `_build_embeddings()`, `_build_llm()`, `_format_docs()` e a implementação de `search_prompt()`.

### Decisões de design

- **LCEL em vez de LLMChain legado**: conforme decisão Q3 da SPEC, usamos o operador `|` (pipe) do LangChain Expression Language, que é o padrão moderno, mais testável e componível.
- **`_build_embeddings()` retorna `None` em vez de `sys.exit()`**: diferente de `ingest.py` (que aborta o processo), `search.py` retorna `None` para permitir que o chamador (`chat.py`) decida como tratar o erro. Isso segue o princípio de separação de preocupações e o requisito R07 da SPEC.
- **`_format_docs()` extraída como função nomeada**: em vez de lambda inline na chain, extraímos como função de módulo para facilitar testes unitários isolados e melhorar legibilidade.
- **`k=10` hardcoded em `search_kwargs`**: conforme DESAFIO e SPEC (R02), o valor não deve ser parametrizado.
- **Modelos LLM leves como default**: `gemini-1.5-flash` e `gpt-4o-mini` foram escolhidos como padrão para minimizar latência e custo, alinhados com o KPI de ≤ 5s do PRD. Ambos são configuráveis via `GOOGLE_LLM_MODEL` / `OPENAI_LLM_MODEL`.
- **`PGVector` instanciado sem `pre_delete_collection`**: ao contrário da ingestão, a busca não deve apagar a coleção — apenas lê os vetores existentes.
- **Importações tardias (lazy imports)**: `langchain_google_genai` e `langchain_openai` são importados dentro das funções para evitar `ImportError` quando apenas um dos provedores está instalado, e para que mocks em testes via `patch.dict("sys.modules", ...)` funcionem corretamente sem necessidade de reload do módulo.

### Dependências adicionadas/atualizadas

- `pytest-cov==7.1.0` — adicionado ao ambiente virtual para geração de relatórios de cobertura. Não adicionado ao `requirements.txt` pois é dependência de desenvolvimento (não runtime).

---

## 2. Relatório de Testes e Cobertura

### Testes criados

**`tests/test_search.py`** — 46 testes organizados em 6 classes:

| Classe | Qtd | O que valida |
|---|---|---|
| `TestPromptTemplate` | 5 | PROMPT_TEMPLATE contém os placeholders, mensagem de recusa e exemplos negativos exigidos pela SPEC |
| `TestBuildEmbeddings` | 7 | Seleção de provedor Google/OpenAI, defaults de modelo, retorno None sem chave, prioridade Google |
| `TestBuildLlm` | 7 | Seleção de LLM Google/OpenAI, defaults de modelo, retorno None sem chave, prioridade Google |
| `TestFormatDocs` | 4 | Concatenação de documentos com `\n\n`, lista vazia, preservação de conteúdo |
| `TestSearchPromptValidation` | 8 | Retorno None para DATABASE_URL ausente, collection ausente, sem API key, falha LLM, falha banco |
| `TestSearchPromptHappyPath` | 13 | Chain retornada não nula, k=10, parâmetros corretos ao PGVector, log de sucesso, provider na mensagem |
| `TestChainStructure` | 2 | PromptTemplate recebe as variáveis corretas e usa o PROMPT_TEMPLATE do módulo sem modificação |

### Resultados da execução

```
============================= test session starts =============================
platform win32 -- Python 3.12.2, pytest-9.1.1, pluggy-1.6.0
plugins: anyio-4.10.0, langsmith-0.4.20, cov-7.1.0
collected 75 items

tests/test_ingest.py  29 passed
tests/test_search.py  46 passed

============================== 75 passed in 3.54s =============================
```

### Cobertura

| Módulo | Linhas | Cobertas | % |
|---|---|---|---|
| `src/__init__.py` | 0 | 0 | 100% |
| `src/chat.py` | 9 | 0 | 0% |
| `src/ingest.py` | 55 | 54 | 98% |
| `src/search.py` | 58 | 58 | 100% |
| **TOTAL** | **122** | **112** | **92%** |

**Cobertura de src/search.py**: 100%

### Casos não cobertos e justificativa

- `src/chat.py` (0%): F03 (Chat RAG) ainda não foi implementada; os testes de `chat.py` serão criados naquela feature.
- `src/ingest.py` linha 184 (`if __name__ == "__main__"`): bloco de entrypoint que só é executado quando o script é chamado diretamente — não coberto intencionalmente, pois exigiria execução do processo Python em um subprocess.

---

## 3. Relatório de Custos de Tokens

> Estimativas baseadas nos preços vigentes do modelo utilizado (claude-sonnet-4-6, agosto 2026).

| Métrica | Valor |
|---|---|
| Tokens de entrada consumidos | ~35.000 |
| Tokens de saída gerados | ~8.000 |
| Modelo utilizado | claude-sonnet-4-6 (1M context) |
| Custo estimado (entrada) | US$ 0,105 |
| Custo estimado (saída) | US$ 0,120 |
| **Custo total estimado** | **US$ 0,225** |

### Notas

- Estimativas calculadas com base no volume aproximado de texto lido (SPEC, PLAN, PRD, ingest.py, test_ingest.py existente) e gerado (search.py completo + test_search.py com 46 testes).
- Preços de referência: claude-sonnet-4-6 — entrada US$ 3/MTok, saída US$ 15/MTok.
- Não houve retrabalho significativo; a implementação seguiu o PLAN.md fielmente.

---

## 4. Próximos Passos Sugeridos

- **F03 (Chat RAG)**: implementar o loop interativo em `src/chat.py` que usa a chain retornada por `search_prompt()`. A interface já está parcialmente definida (importa e chama `search_prompt()`).
- **Teste de integração end-to-end**: após F03, executar teste manual com PDF real para validar as métricas de sucesso da SPEC (≥ 9/10 perguntas corretas, ≥ 90% de recusas corretas, ≤ 5s de latência).
- **Adicionar `pytest-cov` ao `requirements.txt`** ou criar um `requirements-dev.txt` separado para dependências de desenvolvimento.
- **Exibição de metadados de fonte**: consideração futura (P2 na SPEC) — mostrar nome do arquivo e número de página junto com a resposta, usando os metadados de `Document.metadata` preservados pelo `PyPDFLoader`.
