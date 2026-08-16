# PRD — Sistema de Ingestão e Busca Semântica em Documentos PDF

**Versão**: 1.0  
**Data**: 2026-08-16  
**Autor**: Pedro Ratto  
**Contexto**: Desafio MBA — Engenharia de Software com IA  

---

## 1. Sumário Executivo

### Problema
Profissionais e pesquisadores precisam extrair informações específicas de documentos PDF extensos, o que exige leitura manual demorada e está sujeito a falhas humanas — especialmente quando os documentos contêm centenas de páginas ou terminologia técnica densa.

### Solução Proposta
Pipeline RAG (Retrieval-Augmented Generation) que ingere documentos PDF, armazena seu conteúdo como vetores semânticos em um banco de dados PostgreSQL com extensão pgvector, e permite ao usuário fazer perguntas em linguagem natural recebendo respostas fundamentadas **exclusivamente** no conteúdo do documento.

### Critérios de Sucesso (KPIs)

| KPI | Meta |
|---|---|
| Respostas estritamente fundamentadas no PDF | 100% das respostas devem citar ou derivar do contexto recuperado |
| Tempo de resposta end-to-end | ≤ 5 segundos para perguntas sobre coleções de até 500 chunks |
| Completude funcional dos módulos | 3/3 módulos (ingest, search, chat) implementados e executáveis |
| Taxa de recusa correta (fora do contexto) | ≥ 90% de recusas corretas em perguntas sem resposta no documento |
| Setup reproduzível | Execução completa com no máximo 4 comandos após clonar o repositório |

---

## 2. Experiência do Usuário e Funcionalidades

### Personas

**Persona A — Estudante/Pesquisador (Usuário Final)**
- Tem um PDF longo (artigo científico, contrato, manual técnico)
- Quer respostas rápidas sem ler o documento inteiro
- Não tolera respostas inventadas ou incorretas
- Interage via terminal (CLI)

**Persona B — Desenvolvedor/Avaliador (MBA)**
- Avalia a qualidade técnica da implementação
- Verifica se o pipeline RAG segue boas práticas
- Lê o código-fonte e testa o sistema com diferentes PDFs e perguntas

---

### User Stories e Critérios de Aceite

#### US-01 — Ingestão de Documento
> *Como usuário, quero ingerir um documento PDF no sistema para que seu conteúdo fique disponível para consulta semântica.*

**Critérios de Aceite:**
- [ ] O sistema lê o arquivo definido em `PDF_PATH` (variável de ambiente)
- [ ] O PDF é dividido em chunks de **1000 caracteres** com **overlap de 150** (valores obrigatórios pelo DESAFIO)
- [ ] Cada chunk é convertido em vetor (embedding) pelo provedor configurado (Google ou OpenAI)
- [ ] Os vetores são persistidos na coleção definida em `PG_VECTOR_COLLECTION_NAME`
- [ ] O script exibe ao final o número de chunks ingeridos
- [ ] Reexecutar o script não duplica os dados (idempotente ou com limpeza prévia)

#### US-02 — Busca Semântica com RAG
> *Como usuário, quero fazer uma pergunta em linguagem natural e receber uma resposta baseada no conteúdo do PDF.*

**Critérios de Aceite:**
- [ ] A pergunta é transformada em vetor e usada para recuperar os **10 chunks mais relevantes** (`k=10`, via `similarity_search_with_score`) do pgvector
- [ ] Os chunks recuperados são concatenados e injetados no template de prompt definido em `PROMPT_TEMPLATE` (`search.py`)
- [ ] O LLM responde **somente** com base no `{contexto}` fornecido
- [ ] Se a resposta não estiver no documento, o sistema retorna: `"Não tenho informações necessárias para responder sua pergunta."`
- [ ] O sistema nunca produz opiniões, suposições ou informações externas ao documento

#### US-03 — Interface de Chat Interativa
> *Como usuário, quero uma interface de chat em loop para fazer múltiplas perguntas sem reiniciar o programa.*

**Critérios de Aceite:**
- [ ] O chat entra em loop após inicializar a chain RAG
- [ ] O usuário pode digitar perguntas consecutivas
- [ ] A sessão encerra com um comando especial (ex.: `sair`, `exit`, ou `Ctrl+C`)
- [ ] Erros de inicialização (ex.: banco indisponível, API key ausente) são reportados com mensagem clara antes de encerrar

---

### Fora do Escopo (Non-Goals)

- Interface web ou GUI (somente CLI)
- Multi-tenancy ou suporte a múltiplos usuários simultâneos
- Upload de PDFs via interface (o caminho é configurado via variável de ambiente)
- Histórico de conversas persistido entre sessões
- Fine-tuning ou treinamento de modelos
- Suporte a formatos além de PDF (Word, imagens, etc.)
- Autenticação e controle de acesso

---

## 3. Requisitos do Sistema de IA

### Provedores Suportados (configurável via `.env`)

| Componente | Google Generative AI | OpenAI |
|---|---|---|
| Embedding | `models/embedding-001` | `text-embedding-3-small` |
| LLM | Gemini (ex.: `gemini-1.5-flash`) | GPT (ex.: `gpt-4o-mini`) |
| Variável de ativação | `GOOGLE_API_KEY` | `OPENAI_API_KEY` |

### Parâmetros Obrigatórios (fixados pelo DESAFIO)

| Parâmetro | Valor | Local |
|---|---|---|
| `chunk_size` | `1000` caracteres | `src/ingest.py` |
| `chunk_overlap` | `150` caracteres | `src/ingest.py` |
| `k` (top-k retrieval) | `10` | `src/search.py` (`similarity_search_with_score`) |
| Mensagem de recusa | `"Não tenho informações necessárias para responder sua pergunta."` | `src/search.py` |

### Template de Prompt RAG (já definido em `src/search.py`)

O prompt segue o padrão **Context-Only** com exemplos negativos explícitos:

```
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
```

### Estratégia de Avaliação de Qualidade

| Dimensão | Método de Teste | Meta |
|---|---|---|
| Fidelidade ao contexto | Testar 10 perguntas com resposta conhecida no PDF | ≥ 9/10 corretas |
| Recusa de contexto ausente | Testar 5 perguntas fora do escopo do PDF | ≥ 90% recusas corretas |
| Latência | Medir `time` do comando `python src/chat.py` até primeira resposta | ≤ 5s |
| Idempotência | Executar `python src/ingest.py` duas vezes e comparar contagem de chunks | Contagem igual |

---

## 4. Especificações Técnicas

### Arquitetura e Fluxo de Dados

```
┌─────────────┐     ┌──────────────────────────────────────────────────────┐
│  PDF_PATH   │────▶│              src/ingest.py                           │
└─────────────┘     │  1. Carrega PDF (pypdf)                              │
                    │  2. Divide em chunks (RecursiveCharacterTextSplitter) │
                    │  3. Gera embeddings (Google ou OpenAI)                │
                    │  4. Persiste no pgvector (langchain-postgres)         │
                    └──────────────────────────────────────────────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────────────┐
                    │         PostgreSQL 17 + pgvector                    │
                    │   coleção: PG_VECTOR_COLLECTION_NAME                │
                    └─────────────────────────────────────────────────────┘
                                              │
┌─────────────┐     ┌─────────────────────────────────────────────────────┐
│  Pergunta   │────▶│              src/search.py                          │
│  do usuário │     │  1. Gera embedding da pergunta                      │
└─────────────┘     │  2. Busca top-k chunks similares (similarity search)│
                    │  3. Injeta chunks no PROMPT_TEMPLATE                │
                    │  4. Retorna chain (retriever + LLM)                 │
                    └─────────────────────────────────────────────────────┘
                                              │
                    ┌─────────────────────────────────────────────────────┐
                    │              src/chat.py                            │
                    │  1. Inicializa chain via search_prompt()            │
                    │  2. Loop de input do usuário                        │
                    │  3. Invoca chain → imprime resposta                 │
                    └─────────────────────────────────────────────────────┘
```

### Pontos de Integração

| Componente | Tecnologia | Configuração |
|---|---|---|
| Vector Store | PostgreSQL 17 + pgvector (Docker) | `DATABASE_URL` |
| Embedding & LLM | Google GenAI ou OpenAI | `GOOGLE_API_KEY` / `OPENAI_API_KEY` |
| Orquestração RAG | LangChain + langchain-postgres | — |
| PDF Parsing | pypdf | `PDF_PATH` |
| Gerenciamento de env | python-dotenv | `.env` |

### Infraestrutura Docker

```yaml
# docker-compose.yml — dois serviços:
postgres_rag:          # PostgreSQL 17 com pgvector, porta 5432, volume persistente
bootstrap_vector_ext:  # Instala extensão vector (one-shot, roda após postgres estar healthy)
```

### Segurança e Privacidade

- Credenciais de API e banco gerenciadas exclusivamente via `.env` (nunca commitadas)
- Banco acessível apenas localmente (porta 5432 não exposta externamente em produção)
- Dados do PDF ficam armazenados localmente no volume Docker — nenhum dado é enviado a terceiros além das chamadas de embedding/LLM

---

## 5. Riscos e Roadmap

### Riscos Técnicos

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Chunks mal dimensionados geram contexto insuficiente | Média | Alto | Testar `chunk_size` e `chunk_overlap` com o PDF alvo; ajustar até cobertura satisfatória |
| Limite de tokens do LLM excedido pelo contexto | Média | Médio | Limitar `k` (número de chunks recuperados) e tamanho do chunk |
| Latência do provedor de LLM > 5s | Baixa | Médio | Usar modelos leves (Gemini Flash, GPT-4o-mini); medir e documentar |
| Extensão pgvector não instalada corretamente | Baixa | Alto | Serviço `bootstrap_vector_ext` no docker-compose garante instalação automática |
| Ingestão duplicada de dados | Média | Médio | Limpar coleção antes de reingerir ou verificar existência dos chunks |

### Roadmap

#### MVP (Entrega do Desafio)
- [ ] `ingest_pdf()` implementado: carrega, chunka, embeda e persiste no pgvector
- [ ] `search_prompt()` implementado: retriever + chain LangChain com `PROMPT_TEMPLATE`
- [ ] `main()` implementado: loop de chat funcional com tratamento de erros de inicialização
- [ ] README.md atualizado com instruções de execução
- [ ] Testado com ao menos um PDF real (perguntas dentro e fora do contexto)

#### v1.1 — Qualidade e Observabilidade
- [ ] Log do número de chunks ingeridos e tempo de ingestão
- [ ] Exibir fontes (metadados de página) junto com cada resposta
- [ ] Suporte a múltiplos PDFs na mesma coleção

#### v2.0 — Extensibilidade
- [ ] Interface web simples (Streamlit ou FastAPI + frontend básico)
- [ ] Suporte a outros formatos de documento (DOCX, TXT)
- [ ] Cache de embeddings para evitar reprocessamento de documentos já ingeridos
