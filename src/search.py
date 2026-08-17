"""
Módulo de busca semântica RAG para o pipeline de Q&A sobre documentos PDF.

Responsabilidade única (SRP): construir e retornar uma chain LangChain
que recupera os chunks mais relevantes do pgvector e gera respostas
fundamentadas exclusivamente no contexto recuperado.

Fluxo:
    pergunta → PGVector retriever (k=10) → PROMPT_TEMPLATE → LLM → resposta string
"""

import os

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_postgres import PGVector

# Carrega variáveis de ambiente do .env no momento do import.
# As variáveis são lidas sob demanda dentro das funções (não em nível de módulo)
# para que monkeypatch/reload funcionem corretamente em testes.
load_dotenv()

# ---------------------------------------------------------------------------
# Constante: template de prompt RAG (context-only com exemplos negativos).
# Definido pela SPEC e pelo DESAFIO — NÃO alterar sem aprovação explícita.
# O template exige duas variáveis:
#   {contexto}  — chunks recuperados do pgvector, concatenados como string
#   {pergunta}  — pergunta original do usuário, passada via RunnablePassthrough
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """
CONTEXTO:
{contexto}

REGRAS:
- Responda somente com base no CONTEXTO.
- Se a informação não estiver explicitamente no CONTEXTO, responda:
  "Não tenho informações necessárias para responder sua pergunta."
- Nunca invente ou use conhecimento externo.
- Nunca produza opiniões ou interpretações além do que está escrito.

EXEMPLOS DE PERGUNTAS FORA DO CONTEXTO:
Pergunta: "Qual é a capital da França?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Quantos clientes temos em 2024?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

Pergunta: "Você acha isso bom ou ruim?"
Resposta: "Não tenho informações necessárias para responder sua pergunta."

PERGUNTA DO USUÁRIO:
{pergunta}

RESPONDA A "PERGUNTA DO USUÁRIO"
"""


# ---------------------------------------------------------------------------
# Funções auxiliares privadas (responsabilidade única por função)
# ---------------------------------------------------------------------------


def _build_embeddings():
    """Instancia o provedor de embeddings configurado no ambiente.

    O modelo de embedding usado aqui DEVE ser o mesmo utilizado durante
    a ingestão (F01 — src/ingest.py). Provedores diferentes ou modelos
    diferentes produzem vetores com dimensões incompatíveis, causando
    falha silenciosa na busca por similaridade.

    Prioridade: Google Generative AI (se ``GOOGLE_API_KEY`` estiver presente)
    → OpenAI (se ``OPENAI_API_KEY`` estiver presente).

    As variáveis são lidas no momento da chamada (não no import) para que
    alterações via monkeypatch em testes sejam observadas corretamente.

    Returns:
        Instância de embeddings pronta para uso, ou ``None`` se nenhuma
        chave de API estiver configurada.
    """
    if os.getenv("GOOGLE_API_KEY"):
        # Importação tardia: evita ImportError caso o pacote não esteja
        # instalado quando o usuário usa apenas OpenAI.
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        model = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/embedding-001")
        return GoogleGenerativeAIEmbeddings(model=model)

    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import OpenAIEmbeddings

        model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
        return OpenAIEmbeddings(model=model)

    print(
        "Erro: nenhuma chave de API configurada. "
        "Defina GOOGLE_API_KEY ou OPENAI_API_KEY no arquivo .env."
    )
    return None


def _build_llm():
    """Instancia o provedor de LLM configurado no ambiente.

    Utiliza o mesmo mecanismo de seleção de provedor que ``_build_embeddings()``:
    Google tem prioridade quando ``GOOGLE_API_KEY`` está presente; fallback
    para OpenAI caso contrário.

    Modelos padrão configuráveis via variáveis de ambiente:
    - ``GOOGLE_LLM_MODEL``  (default: ``gemini-1.5-flash``)
    - ``OPENAI_LLM_MODEL``  (default: ``gpt-4o-mini``)

    Modelos leves foram escolhidos como default para minimizar latência e custo,
    alinhados com a meta de ≤ 5 segundos de resposta do PRD (KPI de latência).

    As variáveis são lidas no momento da chamada (não no import) para que
    alterações via monkeypatch em testes sejam observadas corretamente.

    Returns:
        Instância de LLM (chat model) pronta para uso, ou ``None`` se nenhuma
        chave de API estiver configurada.
    """
    if os.getenv("GOOGLE_API_KEY"):
        from langchain_google_genai import ChatGoogleGenerativeAI

        model = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash")
        return ChatGoogleGenerativeAI(model=model)

    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI

        model = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        return ChatOpenAI(model=model)

    print(
        "Erro: nenhuma chave de API configurada. "
        "Defina GOOGLE_API_KEY ou OPENAI_API_KEY no arquivo .env."
    )
    return None


def _format_docs(docs: list) -> str:
    """Concatena o conteúdo textual de uma lista de Documents em uma única string.

    Cada chunk é separado por linha em branco dupla para preservar a
    legibilidade quando o contexto é inserido no prompt do LLM.

    Args:
        docs: Lista de objetos ``Document`` retornados pelo retriever.

    Returns:
        String com o conteúdo de todos os documentos concatenados,
        separados por ``\\n\\n``.
    """
    return "\n\n".join(doc.page_content for doc in docs)


# ---------------------------------------------------------------------------
# Função principal (ponto de entrada público do módulo)
# ---------------------------------------------------------------------------


def search_prompt(question=None):
    """Constrói e retorna uma chain LangChain LCEL para RAG sobre o pgvector.

    A chain resultante aceita a pergunta do usuário como string e retorna
    uma resposta gerada exclusivamente com base nos chunks recuperados
    do pgvector. Quando a informação não está nos chunks, o LLM é
    instruído a retornar a mensagem de recusa literal definida no
    ``PROMPT_TEMPLATE``.

    Pipeline interno da chain:
        1. Recebe a pergunta (string) via ``RunnablePassthrough``
        2. Retriever busca os 10 chunks mais similares no pgvector (k=10, fixo)
        3. ``_format_docs()`` concatena os chunks em ``{contexto}``
        4. ``PromptTemplate`` injeta ``{contexto}`` e ``{pergunta}`` no template
        5. LLM gera a resposta
        6. ``StrOutputParser`` converte a saída do LLM em string

    O parâmetro ``question`` existe apenas para compatibilidade futura —
    a chain retornada deve ser invocada com a pergunta via ``.invoke()``.

    Args:
        question: Não utilizado. Reservado para compatibilidade futura.

    Returns:
        Chain LCEL invocável (aceita string, retorna string), ou ``None``
        se houver erro de configuração ou de conexão com o banco.

    Examples:
        >>> chain = search_prompt()
        >>> if chain:
        ...     resposta = chain.invoke("Qual o tema principal do documento?")
        ...     print(resposta)
    """
    # --- Passo 1: validação das variáveis de ambiente obrigatórias ---
    # Fail-fast: verificamos antes de qualquer I/O para dar mensagem clara.
    database_url = os.getenv("DATABASE_URL")
    collection_name = os.getenv("PG_VECTOR_COLLECTION_NAME")

    if not database_url:
        print("Erro: variável de ambiente DATABASE_URL não definida.")
        return None

    if not collection_name:
        print("Erro: variável de ambiente PG_VECTOR_COLLECTION_NAME não definida.")
        return None

    # --- Passo 2: provedor de embeddings ---
    # Deve coincidir com o provedor usado na ingestão (F01) para que as
    # dimensões dos vetores sejam compatíveis com os armazenados no pgvector.
    embeddings = _build_embeddings()
    if embeddings is None:
        return None

    # --- Passo 3: provedor de LLM ---
    llm = _build_llm()
    if llm is None:
        return None

    # --- Passo 4: conexão ao vector store ---
    # PGVector não abre a conexão de rede aqui; apenas instancia o objeto.
    # A conexão efetiva ocorre no momento da busca (retriever.invoke()).
    try:
        vector_store = PGVector(
            embeddings=embeddings,
            collection_name=collection_name,
            connection=database_url,
        )
    except Exception as e:
        print(f"Erro ao conectar ao banco de dados: {e}")
        return None

    # --- Passo 5: retriever com k=10 fixo (requisito obrigatório do DESAFIO) ---
    # k=10 é um parâmetro fixado pela SPEC e não deve ser parametrizado.
    # A busca retorna os 10 chunks mais semanticamente próximos da pergunta.
    retriever = vector_store.as_retriever(search_kwargs={"k": 10})

    # --- Passo 6: montagem da chain LCEL (LangChain Expression Language) ---
    # O operador | (pipe) é o padrão moderno do LangChain.
    # Usamos LCEL em vez de LLMChain legado conforme decisão arquitetural Q3 da SPEC.
    prompt = PromptTemplate(
        input_variables=["contexto", "pergunta"],
        template=PROMPT_TEMPLATE,
    )

    # A chain recebe a pergunta como string:
    # - "contexto": retriever busca chunks → _format_docs concatena em string
    # - "pergunta": passada diretamente ao template sem transformação
    chain = (
        {"contexto": retriever | _format_docs, "pergunta": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )

    # Mensagem de confirmação de inicialização bem-sucedida (R08 da SPEC).
    # Determina qual provedor foi selecionado para o log informativo.
    provider = "Google" if os.getenv("GOOGLE_API_KEY") else "OpenAI"
    print(f"Chain RAG inicializada com provedor {provider} e k=10")

    return chain
