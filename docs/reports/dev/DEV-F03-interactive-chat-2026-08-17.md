# DEV Report — F03 Interactive Chat

**Data**: 2026-08-17
**Autor**: python-senior-dev (agente)
**Branch**: feature/F03-interactive-chat
**Commits**: (pendente — nenhum commit foi criado nesta sessão; alterações permanecem no working tree, aguardando confirmação explícita do usuário)

---

## 1. Relatório de Modificações

### O que foi implementado

Substituição do stub `main()` em `src/chat.py` (que terminava em `pass` logo após a validação de inicialização) por um loop de chat interativo completo via CLI, conforme SPEC/PLAN de F03:

- Inicializa a chain RAG via `search_prompt()` (F02). Se a chain vier `None`, imprime a mensagem de erro obrigatória e encerra com `sys.exit(1)` (R02).
- Exibe mensagem de boas-vindas após inicialização bem-sucedida (R08).
- Entra em loop de leitura de perguntas via `input("Você: ")` (R01, R03).
- Ignora entradas vazias (ou compostas só de espaços) silenciosamente, sem chamar `chain.invoke()` (R07).
- Encerra o loop ao digitar `sair` ou `exit`, case-insensitive, com mensagem de despedida e código de saída 0 (R05).
- Encerra graciosamente em `Ctrl+C` (`KeyboardInterrupt`), sem expor stack trace (R06).
- Trata também `EOFError` (ex.: `Ctrl+D`, pipe fechado) com o mesmo encerramento gracioso — não fazia parte da SPEC, mas é uma extensão de robustez natural do mesmo requisito (R06), evitando stack trace em execuções não interativas/CI.
- Invoca `chain.invoke(pergunta)` e imprime a resposta no formato `"Assistente: <resposta>"` (R04).
- Captura exceções lançadas por `chain.invoke()` (timeout, rate limit, etc.), imprime `"Erro ao processar sua pergunta: <erro>"` e continua o loop sem encerrar a sessão (R09 — P1).

### Arquivos criados

- `tests/test_chat.py` — 27 testes unitários cobrindo todas as ramificações de `main()`.

### Arquivos modificados

- `src/chat.py` — implementação completa do loop de chat, substituindo o stub. Adicionadas constantes de mensagens (`MSG_INIT_FAILURE`, `MSG_WELCOME`, `MSG_FAREWELL`, `PROMPT_USER`, `EXIT_COMMANDS`) para centralizar textos fixos e facilitar asserts nos testes sem duplicar strings literais.

### Decisões de design

- **Import duplo (`try/except ImportError`) para `search_prompt`**: o stub original usava `from search import search_prompt`, que funciona quando o script é executado diretamente (`python src/chat.py`, pois o interpretador adiciona o diretório do script ao `sys.path`), mas falha ao importar o módulo como pacote (`import src.chat`, usado pelos testes com `import src.chat as chat_mod`, seguindo o padrão de `test_search.py`/`test_ingest.py`). A solução aplica fallback para `from src.search import search_prompt`, preservando o modo de execução direto exigido pelo `README`/`CLAUDE.md` (`python src/chat.py`) sem quebrar a testabilidade via import de pacote. Validado manualmente com `python3 -c "import src.chat"` antes e depois da mudança.
- **Constantes de mensagem em vez de strings inline**: `MSG_INIT_FAILURE`, `MSG_WELCOME`, `MSG_FAREWELL`, `PROMPT_USER` e `EXIT_COMMANDS` foram extraídas como constantes de módulo. Isso evita duplicação de literais entre código e testes, e any futura alteração de texto (ex.: internacionalização) fica centralizada em um único ponto — mesmo padrão de constantes usado em `search.py` (`PROMPT_TEMPLATE`).
- **`EOFError` tratado junto com `KeyboardInterrupt`**: não estava explicitamente no PLAN, mas é uma extensão direta do requisito R06 (encerramento gracioso sem stack trace). Sem esse tratamento, rodar `chat.py` em ambientes não interativos (ex.: pipe vazio, testes de CI que fecham stdin) geraria uma exceção não capturada.
- **`sys.exit(1)` apenas no caminho de falha de inicialização**: os caminhos de saída normais (`sair`/`exit`, `Ctrl+C`) usam `break` para sair do loop e retornar de `main()` normalmente, resultando em código de saída 0 por padrão do interpretador — sem necessidade de `sys.exit(0)` explícito, conforme R05/R06.
- **Tratamento de exceções em `chain.invoke()` restrito ao escopo do loop**: usamos `except Exception` (amplo, mas propositalmente) apenas ao redor da chamada ao LLM, para que qualquer falha do provedor (rate limit, timeout, erro de rede) não derrube a sessão inteira — decisão explícita da SPEC (R09/Q2: "continuar é mais robusto").
- **Nenhuma lógica de retrieval/prompt em `chat.py`**: mantendo a separação de responsabilidades já estabelecida — `chat.py` depende apenas da abstração "chain invocável" retornada por `search_prompt()` (Dependency Inversion), sem conhecer detalhes de `PGVector`, embeddings ou `PROMPT_TEMPLATE`.

### Dependências adicionadas/atualizadas

Nenhuma dependência nova adicionada ao projeto. Para viabilizar a execução da suíte de testes neste ambiente (que não possuía `venv` nem pacotes instalados), foram instalados localmente via `pip3 install --user` (não alterando `requirements.txt`, pois já presentes na spec do projeto): `pytest`, `pytest-cov`, `langchain-core`, `langchain-postgres`, `langchain_community`, `langchain_text_splitters`, `langchain_google_genai`, `langchain_openai`.

---

## 2. Relatório de Testes e Cobertura

### Testes criados

**`tests/test_chat.py`** — 27 testes organizados em 7 classes:

| Classe | Qtd | O que valida |
|---|---|---|
| `TestMainInitializationFailure` | 3 | Mensagem de erro, `sys.exit(1)` e ausência de chamada a `input()` quando `search_prompt()` retorna `None` |
| `TestMainWelcomeMessage` | 1 | Mensagem de boas-vindas exibida após inicialização bem-sucedida |
| `TestMainEmptyInput` | 4 | Entrada vazia/espaços em branco não chama `chain.invoke()`, não imprime mensagem extra, loop continua |
| `TestMainExitCommands` | 3 (+6 parametrizados) | `sair`/`exit` em todas as variações de caixa encerram o loop com mensagem de despedida |
| `TestMainKeyboardInterrupt` | 3 | `KeyboardInterrupt` e `EOFError` encerram graciosamente sem propagar exceção; Ctrl+C no meio da sessão interrompe o loop |
| `TestMainChainInvocation` | 4 | `chain.invoke()` chamado com a pergunta correta, resposta impressa no formato esperado, múltiplas perguntas consecutivas, mensagem de recusa repassada corretamente |
| `TestMainChainInvocationErrors` | 3 | Exceções de `chain.invoke()` capturadas, loop continua após erro, `SystemExit` não é levantado indevidamente |
| `TestMainEntrypoint` | 2 | `main()` é chamável; `EXIT_COMMANDS` contém os valores esperados |

### Resultados da execução

```
============================= test session starts ==============================
platform linux -- Python 3.10.12, pytest-9.1.1, pluggy-1.6.0
plugins: langsmith-0.11.0, anyio-4.13.0, cov-7.1.0
collected 103 items

tests/test_chat.py    27 passed
tests/test_ingest.py  29 passed
tests/test_search.py  47 passed

======================== 103 passed, 1 warning in 1.47s ========================
```

(O único warning é um `DeprecationWarning` pré-existente de `langchain-community` em `src/ingest.py`, não relacionado a esta feature.)

### Cobertura

| Módulo | Linhas | Cobertas | % |
|---|---|---|---|
| `src/__init__.py` | 0 | 0 | 100% |
| `src/chat.py` | 37 | 36 | 97% |
| `src/ingest.py` | 55 | 54 | 98% |
| `src/search.py` | 58 | 58 | 100% |
| **TOTAL** | **150** | **148** | **99%** |

**Cobertura de `src/chat.py`**: 97%

### Casos não cobertos e justificativa

- `src/chat.py` linha 116 (`if __name__ == "__main__":`): bloco de entrypoint executado apenas quando o script roda como processo principal — mesmo padrão de não cobertura já aceito em `src/ingest.py` linha 184, pois exigiria execução em subprocess para ser exercitado.

---

## 3. Relatório de Custos de Tokens

> Estimativas baseadas nos preços vigentes do modelo utilizado (claude-sonnet-4-6, agosto 2026). Métricas de tokens da sessão não estão diretamente acessíveis ao agente; os valores abaixo são estimativas por volume de texto processado/gerado.

| Métrica | Valor |
|---|---|
| Tokens de entrada consumidos | ~28.000 |
| Tokens de saída gerados | ~7.500 |
| Modelo utilizado | claude-sonnet-4-6 (Sonnet 5) |
| Custo estimado (entrada) | US$ 0,084 |
| Custo estimado (saída) | US$ 0,113 |
| **Custo total estimado** | **US$ 0,197** |

### Notas

- Estimativa baseada no volume de texto lido (SPEC.md, PLAN.md, PRD.md, search.py, ingest.py, chat.py stub, test_search.py, DEV-F02 report) e gerado (chat.py completo + test_chat.py com 27 testes + este relatório).
- Preços de referência: US$ 3/MTok (entrada) e US$ 15/MTok (saída), mesma referência usada no relatório de F02.
- Não houve retrabalho — a implementação seguiu o PLAN.md com um único ajuste em relação ao pseudocódigo do PLAN: o import de `search_prompt` foi tornado duplo (`try/except`) para suportar tanto a execução direta (`python src/chat.py`) quanto a importação como pacote nos testes (`import src.chat`), algo não coberto explicitamente pelo PLAN mas necessário para testabilidade sem quebrar o modo de execução exigido pelo `CLAUDE.md`.
- Instalação de dependências Python no ambiente de execução (sem `venv` previamente configurado) consumiu tempo de execução de comandos, mas não tokens adicionais de LLM significativos além dos já contabilizados.

---

## 4. Próximos Passos Sugeridos

- **Teste de integração end-to-end manual**: com `.env` configurado e banco populado por `python src/ingest.py`, validar o fluxo completo `python src/chat.py` com perguntas dentro e fora do contexto do PDF, conforme checklist de testes do `PLAN.md` (não executável neste ambiente por falta de credenciais de API e banco PostgreSQL).
- **`requirements-dev.txt`**: as dependências de teste (`pytest`, `pytest-cov`) continuam ausentes de `requirements.txt`; considerar um arquivo de dependências de desenvolvimento separado, como já sugerido no relatório de F02.
- **P2 futuro (fora do escopo de F03)**: exibição de fontes (página/arquivo) junto com a resposta, e modo `--verbose` para depuração dos chunks recuperados, conforme "Future Considerations" da SPEC.
- **Revisão do `README.md`**: confirmar que as instruções de execução (`python src/chat.py`) e o KPI de "4 comandos após clonar o repositório" do PRD estão corretamente documentados após a conclusão do MVP (F01+F02+F03).
