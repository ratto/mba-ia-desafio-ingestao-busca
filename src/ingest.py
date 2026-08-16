"""
Módulo de ingestão de documentos PDF para o pipeline RAG.

Responsabilidade única (SRP): carregar um PDF, dividi-lo em chunks,
gerar embeddings e persistir os vetores no PostgreSQL com pgvector.

Fluxo:
    PDF_PATH → PyPDFLoader → RecursiveCharacterTextSplitter
             → Embeddings (Google ou OpenAI) → PGVector (pgvector)
"""

import os
import sys

from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_core.embeddings import Embeddings
from langchain_postgres import PGVector
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Carrega variáveis de ambiente do .env no momento do import.
# As variáveis são lidas sob demanda dentro das funções (não em nível de módulo)
# para que monkeypatch/reload funcionem corretamente em testes.
load_dotenv()

# ---------------------------------------------------------------------------
# Constantes de chunking — definidas pela SPEC (R02).
# O RecursiveCharacterTextSplitter tenta quebrar em separadores semânticos
# (\n\n → \n → " " → "") antes de cortar no limite, preservando coesão.
# ---------------------------------------------------------------------------

CHUNK_SIZE: int = 1000
CHUNK_OVERLAP: int = 150


# ---------------------------------------------------------------------------
# Funções auxiliares (responsabilidade única por função)
# ---------------------------------------------------------------------------


def _build_embeddings() -> Embeddings:
    """Instancia o provedor de embeddings configurado no ambiente.

    Prioridade: Google Generative AI (se ``GOOGLE_API_KEY`` estiver presente)
    → OpenAI (se ``OPENAI_API_KEY`` estiver presente).

    As variáveis são lidas no momento da chamada (não no import) para que
    alterações via monkeypatch em testes sejam observadas corretamente.

    Returns:
        Instância de :class:`langchain_core.embeddings.Embeddings` pronta para uso.

    Raises:
        SystemExit: se nenhuma chave de API estiver configurada (código 1).
    """
    if os.getenv("GOOGLE_API_KEY"):
        # Importação tardia: evita ImportError caso o pacote não esteja
        # instalado quando o usuário usa apenas OpenAI.
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        model = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/embedding-001")
        print(f"[embed] Usando Google Generative AI — modelo: {model}")
        return GoogleGenerativeAIEmbeddings(model=model)

    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import OpenAIEmbeddings

        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        print(f"[embed] Usando OpenAI — modelo: {model}")
        return OpenAIEmbeddings(model=model)

    print(
        "Erro: nenhuma chave de API configurada. "
        "Defina GOOGLE_API_KEY ou OPENAI_API_KEY no arquivo .env."
    )
    sys.exit(1)


def _validate_environment() -> None:
    """Valida a presença das variáveis de ambiente obrigatórias antes de qualquer I/O.

    Falha rápida (fail-fast): aborta com código de saída 1 e mensagem clara
    se qualquer variável crítica estiver ausente ou se o arquivo PDF não existir.

    Todas as variáveis são lidas no momento da chamada (não no import) para
    suportar testes com monkeypatch sem necessidade de reload do módulo.

    Raises:
        SystemExit: em caso de configuração inválida (código 1).
    """
    pdf_path = os.getenv("PDF_PATH")
    database_url = os.getenv("DATABASE_URL")
    collection_name = os.getenv("PG_VECTOR_COLLECTION_NAME")

    if not pdf_path:
        print("Erro: variável de ambiente PDF_PATH não definida.")
        sys.exit(1)

    if not os.path.exists(pdf_path):
        print(f"Erro: arquivo não encontrado: {pdf_path}")
        sys.exit(1)

    if not database_url:
        print("Erro: variável de ambiente DATABASE_URL não definida.")
        sys.exit(1)

    if not collection_name:
        print("Erro: variável de ambiente PG_VECTOR_COLLECTION_NAME não definida.")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Função principal de ingestão (ponto de entrada público do módulo)
# ---------------------------------------------------------------------------


def ingest_pdf() -> None:
    """Executa o pipeline completo de ingestão de um documento PDF.

    Pipeline:
        1. Valida variáveis de ambiente e existência do arquivo.
        2. Seleciona o provedor de embeddings (Google ou OpenAI).
        3. Carrega o PDF com ``PyPDFLoader`` (uma página por Document).
        4. Divide em chunks usando ``RecursiveCharacterTextSplitter``
           (chunk_size=1000, chunk_overlap=150).
        5. Persiste os vetores no PostgreSQL via ``PGVector.from_documents()``
           com ``pre_delete_collection=True`` para garantir idempotência —
           a coleção é recriada do zero a cada execução, evitando duplicatas.

    Imprime progresso e contagens ao longo da execução para observabilidade
    básica (R07, R08 da SPEC).

    Raises:
        SystemExit: se a configuração for inválida (código 1).
        Exception: exceções do banco ou do provedor de embeddings são
            propagadas com traceback completo para facilitar diagnóstico.
    """
    # Lê as variáveis no momento da execução (não no import) para que
    # testes com monkeypatch possam substituir valores sem reload.
    pdf_path = os.getenv("PDF_PATH")
    database_url = os.getenv("DATABASE_URL")
    collection_name = os.getenv("PG_VECTOR_COLLECTION_NAME")

    # --- Passo 1: validação prévia ---
    _validate_environment()

    # --- Passo 2: provedor de embeddings ---
    embeddings = _build_embeddings()

    # --- Passo 3: carregamento do PDF ---
    # PyPDFLoader preserva metadados de página (source, page) em cada Document,
    # o que permite rastrear a origem de cada chunk posteriormente.
    loader = PyPDFLoader(pdf_path)  # type: ignore[arg-type]  # pdf_path já validado acima
    pages = loader.load()
    print(f"[load]  {len(pages)} página(s) carregada(s) de '{pdf_path}'")

    # --- Passo 4: chunking ---
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(pages)
    print(f"[split] {len(chunks)} chunk(s) gerado(s) "
          f"(chunk_size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    # --- Passo 5: persistência no pgvector ---
    # pre_delete_collection=True garante idempotência: a coleção existente
    # é removida antes de cada ingestão, evitando acúmulo de duplicatas em
    # re-execuções com o mesmo (ou diferente) documento.
    PGVector.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        connection=database_url,
        pre_delete_collection=True,
    )
    print(
        f"[store] Ingestão concluída: {len(chunks)} vetores armazenados "
        f"em '{collection_name}'"
    )


if __name__ == "__main__":
    ingest_pdf()
