"""
Módulo de interface de chat interativo para o pipeline RAG.

Responsabilidade única (SRP): orquestrar o loop de interação com o usuário
via terminal (CLI) — ler perguntas, delegar a busca semântica/RAG para
``search_prompt()`` (F02) e imprimir a resposta do LLM.

Fluxo:
    search_prompt() → chain LCEL
        └─ loop: input("Você: ") → chain.invoke(pergunta) → print("Assistente: ...")

Este módulo é o ponto de entrada final do pipeline (PDF → ingest → search →
chat) e não deve conter lógica de recuperação/prompt — essa responsabilidade
pertence exclusivamente a ``src/search.py`` (Dependency Inversion: ``chat.py``
depende apenas da abstração "chain invocável", não de como ela é construída).
"""

import sys

# Import duplo para suportar dois modos de execução:
# 1) `python src/chat.py` — o diretório do script (src/) é adicionado ao
#    sys.path automaticamente pelo interpretador, então `from search import`
#    resolve diretamente.
# 2) `import src.chat` (usado pelos testes e por outros módulos do pacote)
#    — nesse caso o pacote `src` está no sys.path, não `src/` isoladamente,
#    então é necessário o import qualificado `from src.search import`.
try:
    from search import search_prompt
except ImportError:
    from src.search import search_prompt


# ---------------------------------------------------------------------------
# Mensagens fixas da interface de chat (SPEC F03 — R02, R05, R06, R08, R09).
# Centralizadas como constantes para evitar duplicação e facilitar testes.
# ---------------------------------------------------------------------------

MSG_INIT_FAILURE = (
    "Não foi possível iniciar o chat. Verifique os erros de inicialização."
)
MSG_WELCOME = "Chat RAG iniciado. Digite sua pergunta ou 'sair' para encerrar."
MSG_FAREWELL = "Encerrando o chat. Até logo!"
PROMPT_USER = "Você: "
EXIT_COMMANDS = ("sair", "exit")


def main() -> None:
    """Executa o loop de chat interativo via CLI.

    Pipeline:
        1. Inicializa a chain RAG via ``search_prompt()`` (F02). Se a
           inicialização falhar (``None``), reporta o erro e encerra o
           processo com código de saída 1 (R02, R05 da SPEC).
        2. Exibe mensagem de boas-vindas (R08).
        3. Entra em loop de leitura de input do usuário:
           - Entrada vazia é ignorada silenciosamente, sem chamar o LLM (R07).
           - Comandos ``sair``/``exit`` (case-insensitive) encerram o loop
             com mensagem de despedida e código de saída 0 (R05).
           - ``Ctrl+C`` (``KeyboardInterrupt``) encerra graciosamente, sem
             expor stack trace ao usuário (R06).
           - Exceções durante ``chain.invoke()`` (timeout, rate limit, etc.)
             são capturadas e reportadas sem encerrar o loop (R09 — P1).

    Não retorna valor; efeitos colaterais são I/O de terminal (`print`,
    `input`) e possível `sys.exit(1)` em caso de falha de inicialização.
    """
    # --- Passo 1: inicialização da chain RAG (F02) ---
    # Fail-fast: qualquer erro de configuração (banco, API key) já foi
    # reportado dentro de search_prompt(); aqui apenas decidimos o
    # encerramento do processo com o código de saída apropriado (R02).
    chain = search_prompt()

    if not chain:
        print(MSG_INIT_FAILURE)
        sys.exit(1)

    # --- Passo 2: boas-vindas (R08 — nice-to-have) ---
    print(MSG_WELCOME)

    # --- Passo 3: loop de interação ---
    while True:
        try:
            pergunta = input(PROMPT_USER).strip()
        except KeyboardInterrupt:
            # Ctrl+C durante a espera por input: encerramento gracioso,
            # sem stack trace exposto ao usuário (R06).
            print(f"\n{MSG_FAREWELL}")
            break
        except EOFError:
            # Entrada padrão fechada (ex.: pipe encerrado, `Ctrl+D`):
            # tratamos como encerramento gracioso equivalente ao Ctrl+C,
            # evitando stack trace em execuções não interativas/CI.
            print(f"\n{MSG_FAREWELL}")
            break

        if pergunta.lower() in EXIT_COMMANDS:
            print(MSG_FAREWELL)
            break

        if not pergunta:
            # Entrada vazia é ignorada silenciosamente, sem chamar o LLM
            # e sem imprimir qualquer mensagem (R07).
            continue

        try:
            resposta = chain.invoke(pergunta)
            print(f"Assistente: {resposta}")
        except Exception as e:
            # Erros do LLM (timeout, rate limit, falha de rede) não devem
            # derrubar a sessão de chat — reportamos e continuamos o loop,
            # permitindo ao usuário tentar novamente (R09).
            print(f"Erro ao processar sua pergunta: {e}")


if __name__ == "__main__":
    main()
