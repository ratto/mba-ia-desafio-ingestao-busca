# F02 — Semantic Search (Busca Semântica RAG)

## Problem Statement

Com os vetores persistidos no pgvector pela F01, o sistema ainda não consegue responder perguntas: a função `search_prompt()` em `src/search.py` é um stub que retorna `None`. Sem essa etapa, `src/chat.py` recebe `None` e encerra imediatamente, tornando o pipeline RAG completo inoperante. A ausência dessa feature bloqueia diretamente a entrega do desafio MBA (US-02 e US-03 do PRD).

---

## Goals

1. `search_prompt()` retorna uma chain LangChain funcional capaz de responder perguntas em linguagem natural com base exclusivamente no conteúdo ingerido no pgvector.
2. O retriever recupera os 10 chunks mais relevantes (`k=10`, conforme requisito mandatório do desafio) via busca por similaridade vetorial.
3. O LLM é selecionado pelo mesmo mecanismo de provedor da F01: Google Generative AI com prioridade, fallback para OpenAI.
4. O sistema jamais produz respostas fora do contexto recuperado — quando a informação não está nos chunks, a mensagem de recusa literal é retornada.
5. Erros de inicialização (banco indisponível, API key ausente) são reportados com mensagem clara; a função retorna `None` para que o chamador possa tratar o erro.

---

## Non-Goals

| Fora de escopo | Motivo |
|---|---|
| Interface web ou API REST para consulta | É um CLI; UI é escopo de outra feature |
| Histórico de conversas (memória entre turnos) | O PRD define explicitamente ausência de histórico persistido |
| Reranking ou pós-processamento dos chunks recuperados | Complexidade desproporcional ao escopo do MBA |
| Ajuste dinâmico de `k` | Parâmetro fixado em 10 pelo desafio — não parametrizar |
| Alteração do `PROMPT_TEMPLATE` | Template já definido e aprovado no stub original; fora do escopo desta feature |

---

## User Stories

### Persona A — Estudante / Pesquisador (Usuário Final)

- **US-01** — Como pesquisador, quero fazer uma pergunta sobre o PDF e receber uma resposta direta, para não precisar ler o documento inteiro.
- **US-02** — Como pesquisador, quero que o sistema recuse responder perguntas fora do escopo do documento, para não receber informações inventadas.

### Persona B — Desenvolvedor / Avaliador (MBA)

- **US-03** — Como desenvolvedor, quero que `search_prompt()` retorne uma chain invocável, para que `chat.py` possa usá-la sem alterar sua interface.
- **US-04** — Como desenvolvedor, quero poder usar Google ou OpenAI como provedor de LLM e embeddings, para ter flexibilidade conforme a chave de API disponível.
- **US-05** — Como desenvolvedor, quero que erros de inicialização retornem `None` com mensagem clara, para diagnosticar problemas sem precisar inspecionar stack traces.

---

## Requirements

### Must-Have (P0)

| ID | Requisito | Critério de Aceite |
|---|---|---|
| R01 | Conectar ao pgvector usando `DATABASE_URL` e `PG_VECTOR_COLLECTION_NAME` | Dado o banco acessível com vetores já ingeridos, quando `search_prompt()` é chamado, então `PGVector` é instanciado sem exceção |
| R02 | Criar retriever com `k=10` (valor fixo, não configurável) | Dado o vector store inicializado, quando o retriever é criado, então `search_kwargs={"k": 10}` é passado via `as_retriever()` |
| R03 | Montar chain com `PROMPT_TEMPLATE` já definido em `search.py` | A chain usa exatamente o `PROMPT_TEMPLATE` existente sem modificações |
| R04 | Responder somente com base no contexto recuperado | Dado contexto insuficiente no pgvector, quando o LLM gera resposta, então a saída é a mensagem de recusa literal: `"Não tenho informações necessárias para responder sua pergunta."` |
| R05 | Selecionar provedor de LLM: Google tem prioridade; fallback para OpenAI | Dado `GOOGLE_API_KEY` presente, quando `search_prompt()` é chamado, então o LLM instanciado é da Google Generative AI |
| R06 | Validar presença de pelo menos uma API key antes de instanciar o LLM | Se nenhuma chave estiver configurada, exibir mensagem de erro e retornar `None` |
| R07 | Retornar `None` com mensagem clara em caso de erro de inicialização | Se `DATABASE_URL` ausente ou banco inacessível, imprimir erro e retornar `None` |

### Nice-to-Have (P1)

| ID | Requisito | Critério de Aceite |
|---|---|---|
| R08 | Log de confirmação ao inicializar com sucesso | Após criar a chain, imprimir `"Chain RAG inicializada com provedor <Google/OpenAI> e k=10"` |
| R09 | Separar `_build_llm()` como função auxiliar privada | Facilita teste isolado do provedor de LLM, análogo ao `_build_embeddings()` da F01 |

### Future Considerations (P2)

- Exibir metadados de fonte (nome do arquivo, número de página) junto com cada resposta.
- Suporte a reranking com modelo cross-encoder para melhorar qualidade dos chunks recuperados.
- Cache de resultados para perguntas repetidas na mesma sessão.

---

## Success Metrics

| Indicador | Meta | Como medir |
|---|---|---|
| Fidelidade ao contexto | ≥ 9/10 perguntas com resposta conhecida no PDF respondidas corretamente | Teste manual com 10 perguntas sobre o PDF de referência |
| Taxa de recusa correta | ≥ 90% de recusas em perguntas fora do escopo | Teste manual com 5 perguntas sem resposta no documento |
| Latência da chain (primeira resposta) | ≤ 5 segundos para coleção de até 500 chunks | `time python -c "from src.search import search_prompt; c = search_prompt(); print(c.invoke({'pergunta': 'teste'}))"` |
| `search_prompt()` retorna chain funcional | 100% em ambiente com `.env` correto e banco acessível | Teste unitário de integração |

---

## Open Questions

| # | Questão | Responsável | Bloqueante? |
|---|---|---|---|
| Q1 | Qual LLM específico usar para cada provedor? (ex.: `gemini-1.5-flash` vs `gemini-1.5-pro`; `gpt-4o-mini` vs `gpt-4o`) | Desenvolvedor | Não — default para modelos leves (flash / mini) |
| Q2 | A variável de modelo LLM deve ser configurável via `.env` (ex.: `GOOGLE_LLM_MODEL`, `OPENAI_LLM_MODEL`) ou hardcoded com defaults razoáveis? | Desenvolvedor | Não — default configurável via env é mais flexível |
| Q3 | A chain deve usar `LLMChain` + `PromptTemplate` (legado) ou `LCEL` (pipe `|`)? | Desenvolvedor | Não — LCEL é o padrão moderno do LangChain |

---

## Timeline Considerations

- F02 desbloqueia **F03 (Chat RAG)** — deve ser entregue antes ou em paralelo com F03.
- Depende de **F01 completo** (vetores ingeridos no pgvector) para testes end-to-end.
- Sem novas dependências além das já listadas em `requirements.txt`.
