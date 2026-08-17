"""
Testes unitários para src/search.py — F02 Semantic Search.

Estratégia de isolamento:
- Todas as dependências externas (PGVector, LLM, Embeddings, banco de dados,
  chamadas de API) são substituídas por mocks.
- Os testes verificam o comportamento do módulo (fluxo de chamadas, mensagens
  de erro, retorno de None em erros) sem realizar I/O real.
- As variáveis de ambiente são manipuladas via monkeypatch; como as funções
  de search.py leem os.getenv() no momento da chamada (não no import),
  não é necessário reload do módulo entre testes.

Cobertura alvo: ≥ 80% das linhas de src/search.py.
"""

from unittest.mock import MagicMock, patch, call

import pytest

import src.search as search_mod


# ---------------------------------------------------------------------------
# Fixture global: limpa variáveis de ambiente antes de cada teste
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    """Remove variáveis de ambiente relevantes antes de cada teste.

    Evita contaminação entre testes quando o ambiente local tem .env configurado.
    O fixture é autouse=True, portanto aplicado automaticamente em todos os testes.
    """
    for var in (
        "DATABASE_URL",
        "PG_VECTOR_COLLECTION_NAME",
        "GOOGLE_API_KEY",
        "GOOGLE_EMBEDDING_MODEL",
        "GOOGLE_LLM_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_EMBEDDING_MODEL",
        "OPENAI_LLM_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def valid_env_google(monkeypatch):
    """Configura variáveis de ambiente válidas usando provedor Google."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")
    monkeypatch.setenv("PG_VECTOR_COLLECTION_NAME", "test_collection")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-key")


@pytest.fixture()
def valid_env_openai(monkeypatch):
    """Configura variáveis de ambiente válidas usando apenas provedor OpenAI."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")
    monkeypatch.setenv("PG_VECTOR_COLLECTION_NAME", "test_collection")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")


# ---------------------------------------------------------------------------
# Testes de PROMPT_TEMPLATE
# ---------------------------------------------------------------------------


class TestPromptTemplate:
    """Verifica que o PROMPT_TEMPLATE está correto conforme SPEC e DESAFIO."""

    def test_prompt_template_contains_contexto_placeholder(self):
        """PROMPT_TEMPLATE deve conter o placeholder {contexto}."""
        assert "{contexto}" in search_mod.PROMPT_TEMPLATE

    def test_prompt_template_contains_pergunta_placeholder(self):
        """PROMPT_TEMPLATE deve conter o placeholder {pergunta}."""
        assert "{pergunta}" in search_mod.PROMPT_TEMPLATE

    def test_prompt_template_contains_refusal_message(self):
        """PROMPT_TEMPLATE deve conter a mensagem de recusa literal obrigatória."""
        refusal = "Não tenho informações necessárias para responder sua pergunta."
        assert refusal in search_mod.PROMPT_TEMPLATE

    def test_prompt_template_instructs_context_only(self):
        """PROMPT_TEMPLATE deve instruir resposta baseada somente no CONTEXTO."""
        assert "somente com base no CONTEXTO" in search_mod.PROMPT_TEMPLATE

    def test_prompt_template_contains_negative_examples(self):
        """PROMPT_TEMPLATE deve conter exemplos de perguntas fora do contexto."""
        assert "EXEMPLOS DE PERGUNTAS FORA DO CONTEXTO" in search_mod.PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# Testes de _build_embeddings
# ---------------------------------------------------------------------------


class TestBuildEmbeddings:
    """Testa a seleção automática do provedor de embeddings em search.py."""

    def test_selects_google_when_google_key_present(self, monkeypatch):
        """Deve instanciar GoogleGenerativeAIEmbeddings se GOOGLE_API_KEY estiver presente."""
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
        monkeypatch.setenv("GOOGLE_EMBEDDING_MODEL", "models/embedding-001")

        fake_embeddings = MagicMock()
        fake_google_class = MagicMock(return_value=fake_embeddings)

        with patch.dict("sys.modules", {
            "langchain_google_genai": MagicMock(
                GoogleGenerativeAIEmbeddings=fake_google_class
            )
        }):
            result = search_mod._build_embeddings()

        fake_google_class.assert_called_once_with(model="models/embedding-001")
        assert result is fake_embeddings

    def test_selects_openai_when_only_openai_key_present(self, monkeypatch):
        """Deve instanciar OpenAIEmbeddings se apenas OPENAI_API_KEY estiver presente."""
        monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
        monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        fake_embeddings = MagicMock()
        fake_openai_class = MagicMock(return_value=fake_embeddings)

        with patch.dict("sys.modules", {
            "langchain_openai": MagicMock(OpenAIEmbeddings=fake_openai_class)
        }):
            result = search_mod._build_embeddings()

        fake_openai_class.assert_called_once_with(model="text-embedding-3-small")
        assert result is fake_embeddings

    def test_uses_google_default_model(self, monkeypatch):
        """Deve usar 'models/embedding-001' como default quando GOOGLE_EMBEDDING_MODEL não estiver definido."""
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

        fake_google_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "langchain_google_genai": MagicMock(
                GoogleGenerativeAIEmbeddings=fake_google_class
            )
        }):
            search_mod._build_embeddings()

        fake_google_class.assert_called_once_with(model="models/embedding-001")

    def test_uses_openai_default_model(self, monkeypatch):
        """Deve usar 'text-embedding-3-small' como default quando OPENAI_EMBEDDING_MODEL não estiver definido."""
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key")

        fake_openai_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "langchain_openai": MagicMock(OpenAIEmbeddings=fake_openai_class)
        }):
            search_mod._build_embeddings()

        fake_openai_class.assert_called_once_with(model="text-embedding-3-small")

    def test_returns_none_when_no_api_key(self, capsys):
        """Deve retornar None (não levantar exceção) se nenhuma chave de API estiver definida."""
        result = search_mod._build_embeddings()

        assert result is None

    def test_prints_error_when_no_api_key(self, capsys):
        """Deve imprimir mensagem de erro quando nenhuma chave de API estiver presente."""
        search_mod._build_embeddings()

        captured = capsys.readouterr()
        assert "GOOGLE_API_KEY" in captured.out or "OPENAI_API_KEY" in captured.out

    def test_prefers_google_over_openai_when_both_keys_present(self, monkeypatch):
        """Deve preferir Google quando ambas as chaves estão presentes."""
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-key")
        monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")

        fake_google_class = MagicMock(return_value=MagicMock())
        fake_openai_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "langchain_google_genai": MagicMock(
                GoogleGenerativeAIEmbeddings=fake_google_class
            ),
            "langchain_openai": MagicMock(OpenAIEmbeddings=fake_openai_class),
        }):
            search_mod._build_embeddings()

        fake_google_class.assert_called_once()
        fake_openai_class.assert_not_called()


# ---------------------------------------------------------------------------
# Testes de _build_llm
# ---------------------------------------------------------------------------


class TestBuildLlm:
    """Testa a seleção automática do provedor de LLM em search.py."""

    def test_selects_google_llm_when_google_key_present(self, monkeypatch):
        """Deve instanciar ChatGoogleGenerativeAI se GOOGLE_API_KEY estiver presente."""
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
        monkeypatch.setenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash")

        fake_llm = MagicMock()
        fake_google_class = MagicMock(return_value=fake_llm)

        with patch.dict("sys.modules", {
            "langchain_google_genai": MagicMock(
                ChatGoogleGenerativeAI=fake_google_class
            )
        }):
            result = search_mod._build_llm()

        fake_google_class.assert_called_once_with(model="gemini-1.5-flash")
        assert result is fake_llm

    def test_selects_openai_llm_when_only_openai_key_present(self, monkeypatch):
        """Deve instanciar ChatOpenAI se apenas OPENAI_API_KEY estiver presente."""
        monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
        monkeypatch.setenv("OPENAI_LLM_MODEL", "gpt-4o-mini")

        fake_llm = MagicMock()
        fake_openai_class = MagicMock(return_value=fake_llm)

        with patch.dict("sys.modules", {
            "langchain_openai": MagicMock(ChatOpenAI=fake_openai_class)
        }):
            result = search_mod._build_llm()

        fake_openai_class.assert_called_once_with(model="gpt-4o-mini")
        assert result is fake_llm

    def test_uses_google_default_llm_model(self, monkeypatch):
        """Deve usar 'gemini-1.5-flash' como default quando GOOGLE_LLM_MODEL não estiver definido."""
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

        fake_google_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "langchain_google_genai": MagicMock(
                ChatGoogleGenerativeAI=fake_google_class
            )
        }):
            search_mod._build_llm()

        fake_google_class.assert_called_once_with(model="gemini-1.5-flash")

    def test_uses_openai_default_llm_model(self, monkeypatch):
        """Deve usar 'gpt-4o-mini' como default quando OPENAI_LLM_MODEL não estiver definido."""
        monkeypatch.setenv("OPENAI_API_KEY", "fake-key")

        fake_openai_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "langchain_openai": MagicMock(ChatOpenAI=fake_openai_class)
        }):
            search_mod._build_llm()

        fake_openai_class.assert_called_once_with(model="gpt-4o-mini")

    def test_returns_none_when_no_api_key(self, capsys):
        """Deve retornar None quando nenhuma chave de API estiver configurada."""
        result = search_mod._build_llm()

        assert result is None

    def test_prints_error_when_no_api_key(self, capsys):
        """Deve imprimir mensagem de erro quando nenhuma chave de API estiver presente."""
        search_mod._build_llm()

        captured = capsys.readouterr()
        assert "GOOGLE_API_KEY" in captured.out or "OPENAI_API_KEY" in captured.out

    def test_prefers_google_llm_over_openai_when_both_keys_present(self, monkeypatch):
        """Deve preferir Google LLM quando ambas as chaves estão presentes."""
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-key")
        monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")

        fake_google_class = MagicMock(return_value=MagicMock())
        fake_openai_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "langchain_google_genai": MagicMock(
                ChatGoogleGenerativeAI=fake_google_class
            ),
            "langchain_openai": MagicMock(ChatOpenAI=fake_openai_class),
        }):
            search_mod._build_llm()

        fake_google_class.assert_called_once()
        fake_openai_class.assert_not_called()


# ---------------------------------------------------------------------------
# Testes de _format_docs
# ---------------------------------------------------------------------------


class TestFormatDocs:
    """Testa a função de formatação de documentos para inserção no contexto."""

    def test_formats_single_doc(self):
        """Deve retornar o conteúdo do documento sem separador ao receber lista com um item."""
        doc = MagicMock()
        doc.page_content = "conteúdo do chunk"

        result = search_mod._format_docs([doc])

        assert result == "conteúdo do chunk"

    def test_formats_multiple_docs_with_double_newline(self):
        """Deve separar múltiplos documentos com \\n\\n."""
        doc1 = MagicMock()
        doc1.page_content = "primeiro chunk"
        doc2 = MagicMock()
        doc2.page_content = "segundo chunk"

        result = search_mod._format_docs([doc1, doc2])

        assert result == "primeiro chunk\n\nsegundo chunk"

    def test_formats_empty_list(self):
        """Deve retornar string vazia ao receber lista vazia."""
        result = search_mod._format_docs([])

        assert result == ""

    def test_preserves_content_exactly(self):
        """Deve preservar o conteúdo exato de cada documento, incluindo espaços e quebras."""
        doc = MagicMock()
        doc.page_content = "linha 1\nlinha 2\n  indentado"

        result = search_mod._format_docs([doc])

        assert result == "linha 1\nlinha 2\n  indentado"


# ---------------------------------------------------------------------------
# Testes de search_prompt — erros de validação de ambiente
# ---------------------------------------------------------------------------


class TestSearchPromptValidation:
    """Testa os casos de retorno None por configuração inválida."""

    def test_returns_none_when_database_url_not_set(self, capsys):
        """Deve retornar None se DATABASE_URL não estiver definido."""
        result = search_mod.search_prompt()

        assert result is None

    def test_prints_error_when_database_url_not_set(self, capsys):
        """Deve imprimir mensagem de erro mencionando DATABASE_URL."""
        search_mod.search_prompt()

        captured = capsys.readouterr()
        assert "DATABASE_URL" in captured.out

    def test_returns_none_when_collection_name_not_set(self, monkeypatch, capsys):
        """Deve retornar None se PG_VECTOR_COLLECTION_NAME não estiver definido."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")
        # PG_VECTOR_COLLECTION_NAME ausente

        result = search_mod.search_prompt()

        assert result is None

    def test_prints_error_when_collection_name_not_set(self, monkeypatch, capsys):
        """Deve imprimir mensagem de erro mencionando PG_VECTOR_COLLECTION_NAME."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")

        search_mod.search_prompt()

        captured = capsys.readouterr()
        assert "PG_VECTOR_COLLECTION_NAME" in captured.out

    def test_returns_none_when_no_api_key(self, monkeypatch):
        """Deve retornar None se nenhuma chave de API estiver configurada."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")
        monkeypatch.setenv("PG_VECTOR_COLLECTION_NAME", "test_collection")
        # Sem GOOGLE_API_KEY nem OPENAI_API_KEY

        with patch.object(search_mod, "_build_embeddings", return_value=None):
            result = search_mod.search_prompt()

        assert result is None

    def test_returns_none_when_llm_build_fails(self, valid_env_google):
        """Deve retornar None quando _build_llm falha (retorna None)."""
        with patch.object(search_mod, "_build_embeddings", return_value=MagicMock()), \
             patch.object(search_mod, "_build_llm", return_value=None):
            result = search_mod.search_prompt()

        assert result is None

    def test_returns_none_when_database_connection_fails(self, valid_env_google, capsys):
        """Deve retornar None quando a conexão com o banco de dados falha."""
        fake_embeddings = MagicMock()
        fake_llm = MagicMock()

        with patch.object(search_mod, "_build_embeddings", return_value=fake_embeddings), \
             patch.object(search_mod, "_build_llm", return_value=fake_llm), \
             patch.object(search_mod, "PGVector", side_effect=Exception("conexão recusada")):
            result = search_mod.search_prompt()

        assert result is None

    def test_prints_error_when_database_connection_fails(self, valid_env_google, capsys):
        """Deve imprimir mensagem de erro quando a conexão falha."""
        with patch.object(search_mod, "_build_embeddings", return_value=MagicMock()), \
             patch.object(search_mod, "_build_llm", return_value=MagicMock()), \
             patch.object(search_mod, "PGVector", side_effect=Exception("conexão recusada")):
            search_mod.search_prompt()

        captured = capsys.readouterr()
        assert "Erro" in captured.out


# ---------------------------------------------------------------------------
# Testes de search_prompt — happy path
# ---------------------------------------------------------------------------


class TestSearchPromptHappyPath:
    """Testa o fluxo feliz de search_prompt com dependências mockadas."""

    @pytest.fixture()
    def mocked_pipeline(self, valid_env_google):
        """Configura mocks para o pipeline completo com provedor Google."""
        fake_embeddings = MagicMock()
        fake_llm = MagicMock()
        fake_retriever = MagicMock()
        fake_vector_store = MagicMock()
        fake_vector_store.as_retriever.return_value = fake_retriever

        # Simula a chain LCEL: retorna um MagicMock invocável
        fake_chain = MagicMock()
        fake_chain.invoke.return_value = "resposta do LLM"

        return {
            "fake_embeddings": fake_embeddings,
            "fake_llm": fake_llm,
            "fake_retriever": fake_retriever,
            "fake_vector_store": fake_vector_store,
            "fake_chain": fake_chain,
        }

    def test_returns_non_none_chain_on_happy_path(self, mocked_pipeline):
        """search_prompt deve retornar objeto não-None quando tudo está configurado."""
        mp = mocked_pipeline

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", return_value=mp["fake_vector_store"]):
            result = search_mod.search_prompt()

        assert result is not None

    def test_retriever_configured_with_k_equals_10(self, mocked_pipeline):
        """O retriever deve ser criado com search_kwargs={"k": 10} (valor fixo obrigatório)."""
        mp = mocked_pipeline

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", return_value=mp["fake_vector_store"]):
            search_mod.search_prompt()

        mp["fake_vector_store"].as_retriever.assert_called_once_with(
            search_kwargs={"k": 10}
        )

    def test_pgvector_receives_correct_embeddings(self, mocked_pipeline):
        """PGVector deve ser instanciado com o objeto embeddings correto."""
        mp = mocked_pipeline
        mock_pgvector_class = MagicMock(return_value=mp["fake_vector_store"])

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", mock_pgvector_class):
            search_mod.search_prompt()

        call_kwargs = mock_pgvector_class.call_args.kwargs
        assert call_kwargs.get("embeddings") is mp["fake_embeddings"]

    def test_pgvector_receives_correct_collection_name(self, mocked_pipeline):
        """PGVector deve receber o collection_name da variável de ambiente."""
        mp = mocked_pipeline
        mock_pgvector_class = MagicMock(return_value=mp["fake_vector_store"])

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", mock_pgvector_class):
            search_mod.search_prompt()

        call_kwargs = mock_pgvector_class.call_args.kwargs
        assert call_kwargs.get("collection_name") == "test_collection"

    def test_pgvector_receives_correct_connection_string(self, mocked_pipeline):
        """PGVector deve receber a connection string da variável DATABASE_URL."""
        mp = mocked_pipeline
        mock_pgvector_class = MagicMock(return_value=mp["fake_vector_store"])

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", mock_pgvector_class):
            search_mod.search_prompt()

        call_kwargs = mock_pgvector_class.call_args.kwargs
        assert call_kwargs.get("connection") == "postgresql+psycopg://user:pass@localhost:5432/rag"

    def test_build_embeddings_called_exactly_once(self, mocked_pipeline):
        """_build_embeddings deve ser chamado exatamente uma vez por execução."""
        mp = mocked_pipeline
        mock_build_embeddings = MagicMock(return_value=mp["fake_embeddings"])

        with patch.object(search_mod, "_build_embeddings", mock_build_embeddings), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", return_value=mp["fake_vector_store"]):
            search_mod.search_prompt()

        mock_build_embeddings.assert_called_once()

    def test_build_llm_called_exactly_once(self, mocked_pipeline):
        """_build_llm deve ser chamado exatamente uma vez por execução."""
        mp = mocked_pipeline
        mock_build_llm = MagicMock(return_value=mp["fake_llm"])

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", mock_build_llm), \
             patch.object(search_mod, "PGVector", return_value=mp["fake_vector_store"]):
            search_mod.search_prompt()

        mock_build_llm.assert_called_once()

    def test_prints_success_message_on_initialization(self, mocked_pipeline, capsys):
        """Deve imprimir mensagem de confirmação de inicialização bem-sucedida (R08)."""
        mp = mocked_pipeline

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", return_value=mp["fake_vector_store"]):
            search_mod.search_prompt()

        captured = capsys.readouterr()
        assert "Chain RAG inicializada" in captured.out

    def test_prints_google_provider_in_success_message(self, mocked_pipeline, capsys):
        """A mensagem de sucesso deve mencionar 'Google' quando GOOGLE_API_KEY está presente."""
        mp = mocked_pipeline

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", return_value=mp["fake_vector_store"]):
            search_mod.search_prompt()

        captured = capsys.readouterr()
        assert "Google" in captured.out

    def test_prints_k10_in_success_message(self, mocked_pipeline, capsys):
        """A mensagem de sucesso deve mencionar 'k=10'."""
        mp = mocked_pipeline

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", return_value=mp["fake_vector_store"]):
            search_mod.search_prompt()

        captured = capsys.readouterr()
        assert "k=10" in captured.out

    def test_prints_openai_provider_when_only_openai_key_set(self, valid_env_openai, capsys):
        """A mensagem de sucesso deve mencionar 'OpenAI' quando apenas OPENAI_API_KEY está presente."""
        fake_vector_store = MagicMock()

        with patch.object(search_mod, "_build_embeddings", return_value=MagicMock()), \
             patch.object(search_mod, "_build_llm", return_value=MagicMock()), \
             patch.object(search_mod, "PGVector", return_value=fake_vector_store):
            search_mod.search_prompt()

        captured = capsys.readouterr()
        assert "OpenAI" in captured.out

    def test_returned_chain_is_invocable(self, mocked_pipeline):
        """A chain retornada deve ser um objeto invocável (deve ter método invoke ou __or__)."""
        mp = mocked_pipeline

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", return_value=mp["fake_vector_store"]):
            result = search_mod.search_prompt()

        # A chain LCEL tem método invoke (herdado de Runnable)
        assert hasattr(result, "invoke")

    def test_question_parameter_is_accepted_without_error(self, mocked_pipeline):
        """search_prompt deve aceitar o parâmetro question sem erro (compatibilidade futura)."""
        mp = mocked_pipeline

        with patch.object(search_mod, "_build_embeddings", return_value=mp["fake_embeddings"]), \
             patch.object(search_mod, "_build_llm", return_value=mp["fake_llm"]), \
             patch.object(search_mod, "PGVector", return_value=mp["fake_vector_store"]):
            # Não deve levantar TypeError
            result = search_mod.search_prompt(question="qualquer coisa")

        assert result is not None


# ---------------------------------------------------------------------------
# Testes de integração leve (sem banco real — apenas fluxo da chain)
# ---------------------------------------------------------------------------


class TestChainStructure:
    """Verifica aspectos estruturais da chain montada sem executar chamadas de API."""

    def test_chain_uses_prompt_template_with_correct_variables(self, valid_env_google):
        """A chain deve montar um PromptTemplate com {contexto} e {pergunta}."""
        fake_vector_store = MagicMock()
        captured_prompt = {}

        original_prompt_template = search_mod.PromptTemplate

        def capturing_prompt(**kwargs):
            captured_prompt.update(kwargs)
            return original_prompt_template(**kwargs)

        with patch.object(search_mod, "_build_embeddings", return_value=MagicMock()), \
             patch.object(search_mod, "_build_llm", return_value=MagicMock()), \
             patch.object(search_mod, "PGVector", return_value=fake_vector_store), \
             patch.object(search_mod, "PromptTemplate", side_effect=capturing_prompt):
            search_mod.search_prompt()

        assert "contexto" in captured_prompt.get("input_variables", [])
        assert "pergunta" in captured_prompt.get("input_variables", [])

    def test_chain_uses_existing_prompt_template_constant(self, valid_env_google):
        """A chain deve usar o PROMPT_TEMPLATE do módulo sem modificações."""
        fake_vector_store = MagicMock()
        captured_template = {}

        original_prompt_template = search_mod.PromptTemplate

        def capturing_prompt(**kwargs):
            captured_template["template"] = kwargs.get("template")
            return original_prompt_template(**kwargs)

        with patch.object(search_mod, "_build_embeddings", return_value=MagicMock()), \
             patch.object(search_mod, "_build_llm", return_value=MagicMock()), \
             patch.object(search_mod, "PGVector", return_value=fake_vector_store), \
             patch.object(search_mod, "PromptTemplate", side_effect=capturing_prompt):
            search_mod.search_prompt()

        assert captured_template["template"] == search_mod.PROMPT_TEMPLATE
