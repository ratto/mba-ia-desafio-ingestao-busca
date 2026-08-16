# F03 — Interactive Chat RAG: Implementation Plan

## Overview

Implement `main()` in `src/chat.py` to run an interactive Q&A loop. The function calls `search_prompt()` (from F02) to obtain the RAG chain, then reads user input in a loop, passes each question to the chain, and prints the LLM response until the user exits.

**Entry point**: `python src/chat.py`  
**Key file**: [src/chat.py](../../src/chat.py)

---

## Dependencies

| Source | Purpose |
|---|---|
| `src/search.py` (F02) | `search_prompt()` — returns the RAG chain |
| Python stdlib `sys` | `sys.exit()` for non-zero exit on init failure |

No external packages beyond what F02 already requires.

---

## Environment Variables

F03 has no direct environment variable reads — all configuration is handled by `search_prompt()` in `src/search.py`. The `.env` requirements are the same as F02:

```
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/rag
PG_VECTOR_COLLECTION_NAME=rag_docs
GOOGLE_API_KEY=...   # or OPENAI_API_KEY=...
```

---

## Implementation Steps

### Step 1 — Handle initialization failure

The stub already has this guard. Keep it and add `sys.exit(1)` for proper exit code:

```python
import sys
from search import search_prompt

def main():
    chain = search_prompt()

    if not chain:
        print("Não foi possível iniciar o chat. Verifique os erros de inicialização.")
        sys.exit(1)
```

### Step 2 — Print welcome message and enter loop

```python
    print("Chat RAG iniciado. Digite sua pergunta ou 'sair' para encerrar.")

    while True:
        try:
            pergunta = input("Você: ").strip()
        except KeyboardInterrupt:
            print("\nEncerrando o chat. Até logo!")
            break
```

### Step 3 — Handle exit commands and empty input

```python
        if pergunta.lower() in ("sair", "exit"):
            print("Encerrando o chat. Até logo!")
            break

        if not pergunta:
            continue
```

### Step 4 — Invoke chain and print response

```python
        try:
            resposta = chain.invoke(pergunta)
            print(f"Assistente: {resposta}")
        except Exception as e:
            print(f"Erro ao processar sua pergunta: {e}")
```

---

## Final `src/chat.py`

```python
import sys
from search import search_prompt


def main():
    chain = search_prompt()

    if not chain:
        print("Não foi possível iniciar o chat. Verifique os erros de inicialização.")
        sys.exit(1)

    print("Chat RAG iniciado. Digite sua pergunta ou 'sair' para encerrar.")

    while True:
        try:
            pergunta = input("Você: ").strip()
        except KeyboardInterrupt:
            print("\nEncerrando o chat. Até logo!")
            break

        if pergunta.lower() in ("sair", "exit"):
            print("Encerrando o chat. Até logo!")
            break

        if not pergunta:
            continue

        try:
            resposta = chain.invoke(pergunta)
            print(f"Assistente: {resposta}")
        except Exception as e:
            print(f"Erro ao processar sua pergunta: {e}")


if __name__ == "__main__":
    main()
```

---

## Execution Flow

```
python src/chat.py
        │
        ├─ search_prompt()
        │         └─ None → print erro + sys.exit(1)
        │
        ├─ print "Chat RAG iniciado..."
        │
        └─ loop
                ├─ input("Você: ")
                │         └─ KeyboardInterrupt → print despedida + break
                │
                ├─ pergunta.lower() in ("sair", "exit") → print despedida + break
                │
                ├─ pergunta vazia → continue (sem chamada ao LLM)
                │
                └─ chain.invoke(pergunta)
                          ├─ sucesso → print "Assistente: <resposta>"
                          └─ exceção → print "Erro ao processar..." + continue
```

---

## Testing Checklist

- [ ] Execução normal: `python src/chat.py` inicia, exibe boas-vindas, aceita perguntas e imprime respostas
- [ ] Encerramento com `sair`: digitar `sair` encerra com código 0 e mensagem de despedida
- [ ] Encerramento com `exit`: idem para `exit`, `EXIT`, `Exit` (case-insensitive)
- [ ] Encerramento com Ctrl+C: pressionar Ctrl+C encerra com código 0 e sem stack trace
- [ ] Entrada vazia: pressionar Enter sem texto não chama `chain.invoke()` e o loop continua
- [ ] Falha de inicialização: com `DATABASE_URL` ausente, imprime erro e sai com código 1
- [ ] Verificação de código de saída:
  ```bash
  python src/chat.py; echo "Exit code: $?"
  ```
- [ ] Teste end-to-end manual:
  ```
  $ python src/chat.py
  Chain RAG inicializada com sucesso.
  Chat RAG iniciado. Digite sua pergunta ou 'sair' para encerrar.
  Você: Qual o tema principal do documento?
  Assistente: <resposta baseada no PDF>
  Você: sair
  Encerrando o chat. Até logo!
  ```
