"""
Testes unitários para src/chat.py — F03 Interactive Chat.

Estratégia de isolamento:
- `search_prompt()` (F02) é sempre mockado — nenhuma chamada real a banco de
  dados, embeddings ou LLM é realizada.
- `input()` é mockado via `unittest.mock.patch` com `side_effect` para
  simular sequências de entrada do usuário, incluindo `KeyboardInterrupt`
  e `EOFError`.
- `sys.exit` é mockado quando o teste precisa inspecionar o código de saída
  sem encerrar o processo de teste.

Cobertura alvo: >= 80% das linhas de src/chat.py.
"""

from unittest.mock import MagicMock, patch, call

import pytest

import src.chat as chat_mod


# ---------------------------------------------------------------------------
# Testes de inicialização — falha ao obter a chain (R02, R05 da SPEC)
# ---------------------------------------------------------------------------


class TestMainInitializationFailure:
    """Testa o comportamento de main() quando search_prompt() retorna None."""

    def test_prints_init_failure_message_when_chain_is_none(self, capsys):
        """Deve imprimir a mensagem de falha de inicialização quando a chain é None."""
        with patch.object(chat_mod, "search_prompt", return_value=None), \
             pytest.raises(SystemExit):
            chat_mod.main()

        captured = capsys.readouterr()
        assert chat_mod.MSG_INIT_FAILURE in captured.out

    def test_exits_with_code_1_when_chain_is_none(self):
        """Deve encerrar o processo com código de saída 1 quando a chain é None."""
        with patch.object(chat_mod, "search_prompt", return_value=None):
            with pytest.raises(SystemExit) as exc_info:
                chat_mod.main()

        assert exc_info.value.code == 1

    def test_does_not_enter_loop_when_chain_is_none(self):
        """Não deve chamar input() quando a inicialização falha."""
        with patch.object(chat_mod, "search_prompt", return_value=None), \
             patch("builtins.input") as mock_input, \
             pytest.raises(SystemExit):
            chat_mod.main()

        mock_input.assert_not_called()


# ---------------------------------------------------------------------------
# Testes de boas-vindas e inicialização bem-sucedida (R01, R08)
# ---------------------------------------------------------------------------


class TestMainWelcomeMessage:
    """Testa a exibição da mensagem de boas-vindas após inicialização."""

    def test_prints_welcome_message_after_successful_init(self, capsys):
        """Deve imprimir a mensagem de boas-vindas quando a chain é inicializada com sucesso."""
        fake_chain = MagicMock()

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["sair"]):
            chat_mod.main()

        captured = capsys.readouterr()
        assert chat_mod.MSG_WELCOME in captured.out


# ---------------------------------------------------------------------------
# Testes de entrada vazia (R07)
# ---------------------------------------------------------------------------


class TestMainEmptyInput:
    """Testa que entradas vazias são ignoradas silenciosamente."""

    def test_ignores_empty_input_without_calling_chain(self):
        """Entrada vazia não deve chamar chain.invoke()."""
        fake_chain = MagicMock()

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["", "sair"]):
            chat_mod.main()

        fake_chain.invoke.assert_not_called()

    def test_ignores_whitespace_only_input(self):
        """Entrada contendo apenas espaços em branco deve ser tratada como vazia."""
        fake_chain = MagicMock()

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["   ", "sair"]):
            chat_mod.main()

        fake_chain.invoke.assert_not_called()

    def test_empty_input_does_not_print_extra_message(self, capsys):
        """Entrada vazia não deve imprimir nenhuma mensagem além das esperadas."""
        fake_chain = MagicMock()

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["", "sair"]):
            chat_mod.main()

        captured = capsys.readouterr()
        assert "Assistente:" not in captured.out
        assert "Erro" not in captured.out

    def test_loop_continues_after_empty_input(self):
        """O loop deve continuar após uma entrada vazia, aceitando a próxima pergunta."""
        fake_chain = MagicMock()
        fake_chain.invoke.return_value = "resposta válida"

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["", "Qual o tema?", "sair"]):
            chat_mod.main()

        fake_chain.invoke.assert_called_once_with("Qual o tema?")


# ---------------------------------------------------------------------------
# Testes de comandos de saída (R05)
# ---------------------------------------------------------------------------


class TestMainExitCommands:
    """Testa o encerramento do loop com os comandos 'sair' e 'exit'."""

    @pytest.mark.parametrize("comando", ["sair", "SAIR", "Sair", "exit", "EXIT", "Exit"])
    def test_exits_loop_on_exit_command_case_insensitive(self, comando):
        """Deve encerrar o loop para 'sair'/'exit' em qualquer variação de caixa."""
        fake_chain = MagicMock()

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=[comando]):
            chat_mod.main()  # Não deve travar em loop infinito

        fake_chain.invoke.assert_not_called()

    def test_prints_farewell_message_on_exit_command(self, capsys):
        """Deve imprimir a mensagem de despedida ao digitar 'sair'."""
        fake_chain = MagicMock()

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["sair"]):
            chat_mod.main()

        captured = capsys.readouterr()
        assert chat_mod.MSG_FAREWELL in captured.out

    def test_exit_command_with_surrounding_whitespace(self):
        """Deve reconhecer 'sair'/'exit' mesmo com espaços em branco ao redor."""
        fake_chain = MagicMock()

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["  sair  "]):
            chat_mod.main()

        fake_chain.invoke.assert_not_called()


# ---------------------------------------------------------------------------
# Testes de encerramento gracioso via Ctrl+C / EOF (R06)
# ---------------------------------------------------------------------------


class TestMainKeyboardInterrupt:
    """Testa o encerramento gracioso ao receber KeyboardInterrupt (Ctrl+C)."""

    def test_handles_keyboard_interrupt_without_raising(self, capsys):
        """Deve capturar KeyboardInterrupt sem propagar a exceção (sem stack trace)."""
        fake_chain = MagicMock()

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=KeyboardInterrupt):
            chat_mod.main()  # Não deve levantar exceção

        captured = capsys.readouterr()
        assert chat_mod.MSG_FAREWELL in captured.out

    def test_handles_eof_error_without_raising(self, capsys):
        """Deve capturar EOFError (ex.: Ctrl+D, pipe fechado) sem propagar a exceção."""
        fake_chain = MagicMock()

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=EOFError):
            chat_mod.main()

        captured = capsys.readouterr()
        assert chat_mod.MSG_FAREWELL in captured.out

    def test_keyboard_interrupt_mid_session_ends_loop(self):
        """Ctrl+C no meio de uma sessão ativa deve encerrar o loop imediatamente."""
        fake_chain = MagicMock()
        fake_chain.invoke.return_value = "primeira resposta"

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["primeira pergunta", KeyboardInterrupt]):
            chat_mod.main()

        fake_chain.invoke.assert_called_once_with("primeira pergunta")


# ---------------------------------------------------------------------------
# Testes de invocação da chain e impressão de resposta (R04)
# ---------------------------------------------------------------------------


class TestMainChainInvocation:
    """Testa a chamada da chain com a pergunta do usuário e a impressão da resposta."""

    def test_invokes_chain_with_user_question(self):
        """chain.invoke() deve ser chamado com a pergunta digitada pelo usuário."""
        fake_chain = MagicMock()
        fake_chain.invoke.return_value = "resposta do LLM"

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["Qual o tema principal?", "sair"]):
            chat_mod.main()

        fake_chain.invoke.assert_called_once_with("Qual o tema principal?")

    def test_prints_response_in_expected_format(self, capsys):
        """A resposta deve ser impressa no formato 'Assistente: <resposta>'."""
        fake_chain = MagicMock()
        fake_chain.invoke.return_value = "resposta do LLM"

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["pergunta qualquer", "sair"]):
            chat_mod.main()

        captured = capsys.readouterr()
        assert "Assistente: resposta do LLM" in captured.out

    def test_handles_multiple_consecutive_questions(self):
        """Deve suportar múltiplas perguntas consecutivas na mesma sessão."""
        fake_chain = MagicMock()
        fake_chain.invoke.side_effect = ["resposta 1", "resposta 2"]

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["pergunta 1", "pergunta 2", "sair"]):
            chat_mod.main()

        assert fake_chain.invoke.call_args_list == [
            call("pergunta 1"),
            call("pergunta 2"),
        ]

    def test_prints_refusal_message_when_returned_by_chain(self, capsys):
        """Deve imprimir a mensagem de recusa literal quando retornada pela chain."""
        fake_chain = MagicMock()
        refusal = "Não tenho informações necessárias para responder sua pergunta."
        fake_chain.invoke.return_value = refusal

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["pergunta fora do contexto", "sair"]):
            chat_mod.main()

        captured = capsys.readouterr()
        assert refusal in captured.out


# ---------------------------------------------------------------------------
# Testes de tratamento de exceções durante chain.invoke() (R09)
# ---------------------------------------------------------------------------


class TestMainChainInvocationErrors:
    """Testa a captura de exceções lançadas por chain.invoke() sem encerrar o loop."""

    def test_catches_exception_and_prints_error_message(self, capsys):
        """Deve capturar exceção de chain.invoke() e imprimir mensagem de erro."""
        fake_chain = MagicMock()
        fake_chain.invoke.side_effect = TimeoutError("tempo esgotado")

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["pergunta", "sair"]):
            chat_mod.main()  # Não deve propagar a exceção

        captured = capsys.readouterr()
        assert "Erro ao processar sua pergunta" in captured.out
        assert "tempo esgotado" in captured.out

    def test_loop_continues_after_exception(self):
        """O loop deve continuar após uma exceção, aceitando novas perguntas."""
        fake_chain = MagicMock()
        fake_chain.invoke.side_effect = [Exception("erro temporário"), "resposta ok"]

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["pergunta 1", "pergunta 2", "sair"]):
            chat_mod.main()

        assert fake_chain.invoke.call_count == 2

    def test_does_not_exit_process_on_llm_exception(self):
        """Uma exceção do LLM não deve levantar SystemExit nem encerrar o processo."""
        fake_chain = MagicMock()
        fake_chain.invoke.side_effect = RuntimeError("rate limit excedido")

        with patch.object(chat_mod, "search_prompt", return_value=fake_chain), \
             patch("builtins.input", side_effect=["pergunta", "sair"]):
            try:
                chat_mod.main()
            except SystemExit:
                pytest.fail("main() não deve levantar SystemExit em erro de invoke()")


# ---------------------------------------------------------------------------
# Teste de entrypoint (__main__)
# ---------------------------------------------------------------------------


class TestMainEntrypoint:
    """Verifica que o módulo expõe main() como ponto de entrada executável."""

    def test_main_is_callable(self):
        """A função main() deve estar definida e ser chamável."""
        assert callable(chat_mod.main)

    def test_exit_commands_constant_contains_expected_values(self):
        """EXIT_COMMANDS deve conter 'sair' e 'exit' em minúsculas."""
        assert "sair" in chat_mod.EXIT_COMMANDS
        assert "exit" in chat_mod.EXIT_COMMANDS
