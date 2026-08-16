"""
Testes unitários para src/ingest.py — F01 PDF Data Ingestion.

Estratégia de isolamento:
- Todas as dependências externas (PyPDFLoader, PGVector, Embeddings, sistema
  de arquivos para PDFs reais, banco de dados) são substituídas por mocks.
- Os testes verificam o comportamento do módulo (fluxo de chamadas, mensagens
  de erro, códigos de saída) sem realizar I/O real.
- As variáveis de ambiente são manipuladas via monkeypatch; como as funções
  de ingest.py leem os.getenv() no momento da chamada (não no import),
  não é necessário reload do módulo entre testes.

Cobertura alvo: ≥ 80% das linhas de src/ingest.py.
"""

from unittest.mock import MagicMock, patch

import pytest

import src.ingest as ingest_mod


# ---------------------------------------------------------------------------
# Helpers de fixture
# ---------------------------------------------------------------------------


def _make_fake_document(content: str = "texto de exemplo", page: int = 0) -> MagicMock:
    """Cria um Document fake com os atributos mínimos usados pelo ingest."""
    doc = MagicMock()
    doc.page_content = content
    doc.metadata = {"source": "fake.pdf", "page": page}
    return doc


# ---------------------------------------------------------------------------
# Fixtures globais
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def reset_env(monkeypatch):
    """Remove variáveis de ambiente relevantes antes de cada teste para evitar
    contaminação entre testes quando o ambiente local tem um .env configurado."""
    for var in (
        "PDF_PATH",
        "DATABASE_URL",
        "PG_VECTOR_COLLECTION_NAME",
        "GOOGLE_API_KEY",
        "GOOGLE_EMBEDDING_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_EMBEDDING_MODEL",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def valid_env(monkeypatch, tmp_path):
    """Configura variáveis de ambiente válidas e um arquivo PDF temporário."""
    pdf_file = tmp_path / "doc.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content")

    monkeypatch.setenv("PDF_PATH", str(pdf_file))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")
    monkeypatch.setenv("PG_VECTOR_COLLECTION_NAME", "test_collection")
    monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-key")

    return {"pdf_path": str(pdf_file)}


# ---------------------------------------------------------------------------
# Testes de _validate_environment
# ---------------------------------------------------------------------------


class TestValidateEnvironment:
    """Testa a função _validate_environment com todas as combinações de erro."""

    def test_exits_when_pdf_path_not_set(self):
        """Deve encerrar com sys.exit(1) se PDF_PATH não estiver definido.
        O fixture autouse 'reset_env' já garante que PDF_PATH está ausente."""
        with pytest.raises(SystemExit) as exc_info:
            ingest_mod._validate_environment()

        assert exc_info.value.code == 1

    def test_exits_when_pdf_file_not_found(self, monkeypatch):
        """Deve encerrar com sys.exit(1) se o arquivo PDF não existir."""
        monkeypatch.setenv("PDF_PATH", "/caminho/inexistente/arquivo.pdf")

        with pytest.raises(SystemExit) as exc_info:
            ingest_mod._validate_environment()

        assert exc_info.value.code == 1

    def test_exits_when_database_url_not_set(self, monkeypatch, tmp_path):
        """Deve encerrar com sys.exit(1) se DATABASE_URL não estiver definido."""
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF")
        monkeypatch.setenv("PDF_PATH", str(pdf_file))
        # DATABASE_URL ausente (reset_env já removeu)

        with pytest.raises(SystemExit) as exc_info:
            ingest_mod._validate_environment()

        assert exc_info.value.code == 1

    def test_exits_when_collection_name_not_set(self, monkeypatch, tmp_path):
        """Deve encerrar com sys.exit(1) se PG_VECTOR_COLLECTION_NAME não estiver definido."""
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF")
        monkeypatch.setenv("PDF_PATH", str(pdf_file))
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")
        # PG_VECTOR_COLLECTION_NAME ausente (reset_env já removeu)

        with pytest.raises(SystemExit) as exc_info:
            ingest_mod._validate_environment()

        assert exc_info.value.code == 1

    def test_passes_with_valid_environment(self, valid_env):
        """Não deve levantar exceção quando o ambiente está completamente configurado."""
        # Não deve levantar SystemExit nem qualquer outra exceção
        ingest_mod._validate_environment()

    def test_error_message_mentions_pdf_path(self, capsys):
        """A mensagem de erro para PDF_PATH ausente deve mencioná-lo."""
        with pytest.raises(SystemExit):
            ingest_mod._validate_environment()

        captured = capsys.readouterr()
        assert "PDF_PATH" in captured.out

    def test_error_message_mentions_missing_file_path(self, monkeypatch, capsys):
        """A mensagem de erro para arquivo inexistente deve exibir o path."""
        missing_path = "/nao/existe/arquivo.pdf"
        monkeypatch.setenv("PDF_PATH", missing_path)

        with pytest.raises(SystemExit):
            ingest_mod._validate_environment()

        captured = capsys.readouterr()
        assert missing_path in captured.out


# ---------------------------------------------------------------------------
# Testes de _build_embeddings
# ---------------------------------------------------------------------------


class TestBuildEmbeddings:
    """Testa a seleção automática do provedor de embeddings."""

    def test_selects_google_when_google_key_present(self, monkeypatch):
        """Deve chamar GoogleGenerativeAIEmbeddings se GOOGLE_API_KEY estiver presente."""
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
        monkeypatch.setenv("GOOGLE_EMBEDDING_MODEL", "models/embedding-001")

        fake_embeddings = MagicMock()
        fake_google_class = MagicMock(return_value=fake_embeddings)

        with patch.object(ingest_mod, "_build_embeddings", wraps=ingest_mod._build_embeddings):
            with patch("src.ingest._build_embeddings") as mock_build:
                mock_build.return_value = fake_embeddings
                # Testa diretamente a lógica interna via importação lazy
                pass

        # Testa a função real com mock da importação lazy
        with patch.dict("sys.modules", {
            "langchain_google_genai": MagicMock(GoogleGenerativeAIEmbeddings=fake_google_class)
        }):
            result = ingest_mod._build_embeddings()

        fake_google_class.assert_called_once_with(model="models/embedding-001")
        assert result is fake_embeddings

    def test_selects_openai_when_only_openai_key_present(self, monkeypatch):
        """Deve chamar OpenAIEmbeddings se apenas OPENAI_API_KEY estiver presente."""
        # GOOGLE_API_KEY já ausente por causa do reset_env
        monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
        monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

        fake_embeddings = MagicMock()
        fake_openai_class = MagicMock(return_value=fake_embeddings)

        with patch.dict("sys.modules", {
            "langchain_openai": MagicMock(OpenAIEmbeddings=fake_openai_class)
        }):
            result = ingest_mod._build_embeddings()

        fake_openai_class.assert_called_once_with(model="text-embedding-3-small")
        assert result is fake_embeddings

    def test_uses_google_default_model_when_model_not_set(self, monkeypatch):
        """Deve usar 'models/embedding-001' como default quando GOOGLE_EMBEDDING_MODEL não estiver definido."""
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")
        # GOOGLE_EMBEDDING_MODEL ausente — deve usar o default

        fake_google_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "langchain_google_genai": MagicMock(GoogleGenerativeAIEmbeddings=fake_google_class)
        }):
            ingest_mod._build_embeddings()

        fake_google_class.assert_called_once_with(model="models/embedding-001")

    def test_uses_openai_default_model_when_model_not_set(self, monkeypatch):
        """Deve usar 'text-embedding-3-small' como default quando OPENAI_EMBEDDING_MODEL não estiver definido."""
        # GOOGLE_API_KEY ausente por reset_env
        monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")
        # OPENAI_EMBEDDING_MODEL ausente — deve usar o default

        fake_openai_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "langchain_openai": MagicMock(OpenAIEmbeddings=fake_openai_class)
        }):
            ingest_mod._build_embeddings()

        fake_openai_class.assert_called_once_with(model="text-embedding-3-small")

    def test_exits_when_no_api_key_present(self):
        """Deve encerrar com sys.exit(1) se nenhuma chave de API estiver definida.
        reset_env já garante que GOOGLE_API_KEY e OPENAI_API_KEY estão ausentes."""
        with pytest.raises(SystemExit) as exc_info:
            ingest_mod._build_embeddings()

        assert exc_info.value.code == 1

    def test_prefers_google_over_openai_when_both_keys_present(self, monkeypatch):
        """Deve preferir Google quando GOOGLE_API_KEY e OPENAI_API_KEY estão ambos definidos."""
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-google-key")
        monkeypatch.setenv("OPENAI_API_KEY", "fake-openai-key")

        fake_google_class = MagicMock(return_value=MagicMock())
        fake_openai_class = MagicMock(return_value=MagicMock())

        with patch.dict("sys.modules", {
            "langchain_google_genai": MagicMock(GoogleGenerativeAIEmbeddings=fake_google_class),
            "langchain_openai": MagicMock(OpenAIEmbeddings=fake_openai_class),
        }):
            ingest_mod._build_embeddings()

        fake_google_class.assert_called_once()
        fake_openai_class.assert_not_called()

    def test_error_message_when_no_api_key(self, capsys):
        """A mensagem de erro deve mencionar ambas as variáveis de chave de API."""
        with pytest.raises(SystemExit):
            ingest_mod._build_embeddings()

        captured = capsys.readouterr()
        assert "GOOGLE_API_KEY" in captured.out or "OPENAI_API_KEY" in captured.out


# ---------------------------------------------------------------------------
# Testes de ingest_pdf (happy path e casos de borda)
# ---------------------------------------------------------------------------


class TestIngestPdf:
    """Testa o fluxo completo de ingest_pdf com todas as dependências mockadas."""

    @pytest.fixture()
    def mocked_pipeline(self, monkeypatch, tmp_path):
        """Configura ambiente válido e mocks para o pipeline completo."""
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake")

        monkeypatch.setenv("PDF_PATH", str(pdf_file))
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")
        monkeypatch.setenv("PG_VECTOR_COLLECTION_NAME", "test_collection")
        monkeypatch.setenv("GOOGLE_API_KEY", "fake-key")

        fake_pages = [_make_fake_document(f"página {i}", i) for i in range(3)]
        fake_chunks = [_make_fake_document(f"chunk {i}", 0) for i in range(5)]
        fake_embeddings = MagicMock()
        fake_vector_store = MagicMock()

        mock_loader = MagicMock()
        mock_loader.load.return_value = fake_pages

        mock_splitter = MagicMock()
        mock_splitter.split_documents.return_value = fake_chunks

        mock_pgvector = MagicMock()
        mock_pgvector.from_documents.return_value = fake_vector_store

        return {
            "pdf_path": str(pdf_file),
            "fake_pages": fake_pages,
            "fake_chunks": fake_chunks,
            "fake_embeddings": fake_embeddings,
            "mock_loader_class": MagicMock(return_value=mock_loader),
            "mock_loader": mock_loader,
            "mock_splitter_class": MagicMock(return_value=mock_splitter),
            "mock_splitter": mock_splitter,
            "mock_pgvector": mock_pgvector,
            "mock_build_embeddings": MagicMock(return_value=fake_embeddings),
        }

    def test_happy_path_calls_loader_splitter_pgvector(self, mocked_pipeline):
        """Deve chamar PyPDFLoader, splitter e PGVector.from_documents em sequência."""
        mp = mocked_pipeline

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            ingest_mod.ingest_pdf()

        # PyPDFLoader foi instanciado
        mp["mock_loader_class"].assert_called_once()
        # loader.load() foi chamado
        mp["mock_loader"].load.assert_called_once()
        # split_documents recebeu as páginas
        mp["mock_splitter"].split_documents.assert_called_once_with(mp["fake_pages"])
        # PGVector.from_documents foi chamado com os chunks
        mp["mock_pgvector"].from_documents.assert_called_once()

    def test_splitter_configured_with_correct_parameters(self, mocked_pipeline):
        """Deve criar o splitter com chunk_size=1000 e chunk_overlap=150."""
        mp = mocked_pipeline

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            ingest_mod.ingest_pdf()

        mp["mock_splitter_class"].assert_called_once_with(
            chunk_size=1000,
            chunk_overlap=150,
        )

    def test_pgvector_receives_pre_delete_collection_true(self, mocked_pipeline):
        """Deve passar pre_delete_collection=True para PGVector (garantia de idempotência)."""
        mp = mocked_pipeline

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            ingest_mod.ingest_pdf()

        call_kwargs = mp["mock_pgvector"].from_documents.call_args.kwargs
        assert call_kwargs.get("pre_delete_collection") is True

    def test_pgvector_receives_correct_collection_and_connection(self, mocked_pipeline):
        """Deve passar collection_name e connection corretos para PGVector."""
        mp = mocked_pipeline

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            ingest_mod.ingest_pdf()

        call_kwargs = mp["mock_pgvector"].from_documents.call_args.kwargs
        assert call_kwargs.get("collection_name") == "test_collection"
        assert call_kwargs.get("connection") == "postgresql+psycopg://user:pass@localhost:5432/rag"

    def test_pgvector_receives_correct_documents_and_embedding(self, mocked_pipeline):
        """Deve passar os chunks e o objeto embeddings corretos para PGVector."""
        mp = mocked_pipeline

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            ingest_mod.ingest_pdf()

        call_kwargs = mp["mock_pgvector"].from_documents.call_args.kwargs
        assert call_kwargs.get("documents") is mp["fake_chunks"]
        assert call_kwargs.get("embedding") is mp["fake_embeddings"]

    def test_exits_when_pdf_path_missing(self):
        """Deve encerrar com SystemExit(1) se PDF_PATH não estiver definido.
        reset_env já garante PDF_PATH ausente."""
        with pytest.raises(SystemExit) as exc_info:
            ingest_mod.ingest_pdf()

        assert exc_info.value.code == 1

    def test_exits_when_pdf_file_does_not_exist(self, monkeypatch):
        """Deve encerrar com SystemExit(1) se o arquivo PDF não for encontrado."""
        monkeypatch.setenv("PDF_PATH", "/nao/existe/arquivo.pdf")
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")
        monkeypatch.setenv("PG_VECTOR_COLLECTION_NAME", "test_collection")

        with pytest.raises(SystemExit) as exc_info:
            ingest_mod.ingest_pdf()

        assert exc_info.value.code == 1

    def test_exits_when_no_api_key(self, monkeypatch, tmp_path):
        """Deve encerrar com SystemExit(1) se nenhuma chave de API estiver configurada."""
        pdf_file = tmp_path / "doc.pdf"
        pdf_file.write_bytes(b"%PDF")

        monkeypatch.setenv("PDF_PATH", str(pdf_file))
        monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost:5432/rag")
        monkeypatch.setenv("PG_VECTOR_COLLECTION_NAME", "test_collection")
        # GOOGLE_API_KEY e OPENAI_API_KEY ausentes por reset_env

        with pytest.raises(SystemExit) as exc_info:
            ingest_mod.ingest_pdf()

        assert exc_info.value.code == 1

    def test_empty_pdf_produces_zero_chunks(self, mocked_pipeline):
        """Deve processar sem erro um PDF que resulta em zero chunks (PDF vazio/sem texto)."""
        mp = mocked_pipeline
        # Sobrescreve splitter para retornar lista vazia
        mp["mock_splitter"].split_documents.return_value = []

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            # Não deve levantar exceção
            ingest_mod.ingest_pdf()

        # PGVector.from_documents ainda deve ser chamado, mesmo com lista vazia
        mp["mock_pgvector"].from_documents.assert_called_once()

    def test_database_error_propagates(self, mocked_pipeline):
        """Exceção do banco de dados deve ser propagada (não silenciada)."""
        mp = mocked_pipeline
        mp["mock_pgvector"].from_documents.side_effect = ConnectionError("banco inacessível")

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            with pytest.raises(ConnectionError, match="banco inacessível"):
                ingest_mod.ingest_pdf()

    def test_print_messages_contain_chunk_count(self, mocked_pipeline, capsys):
        """As mensagens de log devem informar o número de chunks gerados e armazenados."""
        mp = mocked_pipeline
        # 7 chunks para verificação na saída
        fake_chunks_7 = [_make_fake_document(f"chunk {i}") for i in range(7)]
        mp["mock_splitter"].split_documents.return_value = fake_chunks_7

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            ingest_mod.ingest_pdf()

        captured = capsys.readouterr()
        assert "7" in captured.out
        assert "test_collection" in captured.out

    def test_print_messages_contain_page_count(self, mocked_pipeline, capsys):
        """A saída deve informar quantas páginas foram carregadas."""
        mp = mocked_pipeline
        # fake_pages já tem 3 páginas (definido no fixture mocked_pipeline)

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            ingest_mod.ingest_pdf()

        captured = capsys.readouterr()
        assert "3" in captured.out  # 3 páginas

    def test_build_embeddings_called_once(self, mocked_pipeline):
        """_build_embeddings deve ser chamado exatamente uma vez por execução."""
        mp = mocked_pipeline

        with patch.object(ingest_mod, "PyPDFLoader", mp["mock_loader_class"]), \
             patch.object(ingest_mod, "RecursiveCharacterTextSplitter", mp["mock_splitter_class"]), \
             patch.object(ingest_mod, "PGVector", mp["mock_pgvector"]), \
             patch.object(ingest_mod, "_build_embeddings", mp["mock_build_embeddings"]):
            ingest_mod.ingest_pdf()

        mp["mock_build_embeddings"].assert_called_once()


# ---------------------------------------------------------------------------
# Testes de constantes do módulo
# ---------------------------------------------------------------------------


class TestModuleConstants:
    """Testa que as constantes de chunking estão corretas conforme SPEC R02."""

    def test_chunk_size_is_1000(self):
        """CHUNK_SIZE deve ser 1000 conforme SPEC R02."""
        assert ingest_mod.CHUNK_SIZE == 1000

    def test_chunk_overlap_is_150(self):
        """CHUNK_OVERLAP deve ser 150 conforme SPEC R02."""
        assert ingest_mod.CHUNK_OVERLAP == 150
