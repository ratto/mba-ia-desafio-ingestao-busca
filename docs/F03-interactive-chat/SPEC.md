# F03 — Interactive Chat RAG (Chat Interativo)

## Problem Statement

Com a chain RAG funcional entregue pela F02, o pipeline ainda não tem interface de uso: `main()` em `src/chat.py` obtém a chain mas termina imediatamente no `pass` do stub, sem entrar em loop. O usuário final não consegue fazer perguntas ao documento sem alterar o código. Essa feature é a última peça que fecha o ciclo completo do desafio MBA — sem ela, as features F01 e F02 existem mas não são acessíveis.

---

## Goals

1. O usuário consegue iniciar uma sessão de Q&A sobre o PDF com um único comando (`python src/chat.py`) e fazer perguntas consecutivas sem reiniciar o programa.
2. A sessão encerra de forma limpa ao digitar `sair`, `exit` (case-insensitive) ou pressionar Ctrl+C — sem stack trace exposto ao usuário.
3. Erros de inicialização (banco indisponível, API key ausente, `search_prompt()` retorna `None`) são reportados com mensagem clara e o programa encerra com código de saída não-zero antes de entrar no loop.
4. Entradas vazias são ignoradas silenciosamente, sem chamar o LLM e sem mensagem de erro.
5. O sistema completo (ingest → search → chat) é executável com no máximo 4 comandos após clonar o repositório, conforme KPI do PRD.

---

## Non-Goals

| Fora de escopo | Motivo |
|---|---|
| Interface web, GUI ou API REST | O PRD define CLI exclusivamente |
| Histórico de conversas persistido entre sessões | PRD lista explicitamente como non-goal |
| Memória de contexto entre turnos da mesma sessão (conversational memory) | Adiciona complexidade e latência; o RAG já provê contexto por chunk — histórico de chat é v2.0 |
| Múltiplos usuários simultâneos | O CLI é single-user por design |
| Comandos especiais além de `sair`/`exit` (ex.: `/help`, `/clear`) | Fora do escopo mínimo do desafio |

---

## User Stories

### Persona A — Estudante / Pesquisador (Usuário Final)

- **US-01** — Como pesquisador, quero iniciar o chat com um comando simples e fazer várias perguntas sobre o PDF sem reiniciar, para ter uma sessão fluida de consulta.
- **US-02** — Como pesquisador, quero encerrar o chat digitando `sair` ou `exit`, para sair do programa de forma controlada sem precisar forçar o encerramento (Ctrl+C).
- **US-03** — Como pesquisador, quero que o programa informe claramente quando não conseguiu iniciar por problemas de configuração, para saber o que corrigir no `.env`.

### Persona B — Desenvolvedor / Avaliador (MBA)

- **US-04** — Como desenvolvedor, quero que `chat.py` seja executável diretamente com `python src/chat.py`, para poder demonstrar o sistema completo sem etapas adicionais.
- **US-05** — Como desenvolvedor, quero que o programa encerre com código de saída 1 em caso de falha de inicialização, para integração com scripts de CI/CD.

---

## Requirements

### Must-Have (P0)

| ID | Requisito | Critério de Aceite |
|---|---|---|
| R01 | Inicializar a chain RAG via `search_prompt()` antes de entrar no loop | Dado `.env` correto e banco acessível, quando `python src/chat.py` é executado, então a chain é criada e o prompt de entrada é exibido |
| R02 | Encerrar com mensagem clara se `search_prompt()` retornar `None` | Dado erro de inicialização (banco, API key), quando `main()` é chamado, então o programa imprime `"Não foi possível iniciar o chat. Verifique os erros de inicialização."` e sai com código 1 |
| R03 | Entrar em loop de input após inicialização bem-sucedida | Dado chain inicializada, quando o prompt `"Você: "` é exibido, então o programa aguarda input do usuário indefinidamente |
| R04 | Passar a pergunta do usuário à chain e imprimir a resposta | Dado pergunta válida digitada pelo usuário, quando Enter é pressionado, então `chain.invoke(pergunta)` é chamado e a resposta é impressa no formato `"Assistente: <resposta>"` |
| R05 | Encerrar o loop ao digitar `sair` ou `exit` (case-insensitive) | Dado o loop ativo, quando o usuário digita `sair`, `SAIR`, `exit` ou `EXIT`, então o programa imprime mensagem de despedida e encerra com código 0 |
| R06 | Encerrar graciosamente com Ctrl+C (KeyboardInterrupt) | Dado o loop ativo, quando o usuário pressiona Ctrl+C, então o programa captura o sinal, imprime mensagem de encerramento e sai com código 0 — sem stack trace |
| R07 | Ignorar entradas vazias silenciosamente | Dado o loop ativo, quando o usuário pressiona Enter sem digitar nada, então o loop reinicia sem chamar `chain.invoke()` e sem imprimir mensagem |

### Nice-to-Have (P1)

| ID | Requisito | Critério de Aceite |
|---|---|---|
| R08 | Mensagem de boas-vindas ao iniciar | Após chain inicializada, imprimir `"Chat RAG iniciado. Digite sua pergunta ou 'sair' para encerrar."` |
| R09 | Tratamento de exceções do LLM durante o loop | Se `chain.invoke()` lançar exceção (timeout, rate limit), capturar, imprimir `"Erro ao processar sua pergunta: <erro>"` e continuar o loop sem encerrar |

### Future Considerations (P2)

- Memória de contexto entre turnos (conversational memory via `ConversationBufferMemory`).
- Exibir fontes (nome do arquivo, número de página) junto com cada resposta.
- Modo `--verbose` para depuração que exibe os chunks recuperados antes da resposta.

---

## Success Metrics

| Indicador | Meta | Como medir |
|---|---|---|
| Completude funcional | `python src/chat.py` inicia, aceita perguntas e encerra com `sair` — sem erros | Execução manual end-to-end |
| Tempo até primeira resposta | ≤ 5 segundos após digitar a pergunta (para coleção ≤ 500 chunks) | `time` no terminal |
| Taxa de encerramento limpo | 100% — Ctrl+C e `sair`/`exit` nunca expõem stack trace | Teste manual |
| Respostas corretas sobre o PDF | ≥ 9/10 em perguntas com resposta conhecida no documento | Teste manual com 10 perguntas |

---

## Open Questions

| # | Questão | Responsável | Bloqueante? |
|---|---|---|---|
| Q1 | O prompt do usuário deve ser colorido (ex.: ANSI escape codes para `"Você: "` em azul) ou texto simples? | Desenvolvedor | Não — texto simples é suficiente para o MVP |
| Q2 | Erros durante `chain.invoke()` devem encerrar o programa ou continuar o loop? | Desenvolvedor | Não — continuar (P1 R09) é mais robusto, mas encerrar é aceitável para MVP |

---

## Timeline Considerations

- F03 é a **última feature** do MVP — desbloqueia a entrega completa do desafio.
- Depende de **F02 completo** (`search_prompt()` retornando chain funcional).
- Complexidade de implementação muito baixa — `main()` é ~20 linhas de código real.
- Pode ser desenvolvida em paralelo com F02 usando o stub existente de `search_prompt()`.
