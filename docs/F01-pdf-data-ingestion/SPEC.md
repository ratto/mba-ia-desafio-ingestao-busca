# F01 — PDF Data Ingestion

## Problem Statement

O pipeline RAG precisa de uma base de conhecimento vetorial populada antes de qualquer consulta semântica. Sem essa etapa de ingestão, o sistema não tem contexto para responder perguntas e toda a cadeia downstream (`search.py`, `chat.py`) torna-se inoperante. A ausência dessa feature bloqueia completamente a entrega do desafio MBA.

---

## Goals

1. O sistema lê com sucesso qualquer PDF válido apontado por `PDF_PATH` e persiste todos os seus chunks no banco vetorial em uma única execução de `python src/ingest.py`.
2. Cada chunk respeita o tamanho de 1 000 caracteres com overlap de 150, garantindo que nenhum trecho relevante seja partido sem continuidade.
3. Os vetores são armazenados na coleção `PG_VECTOR_COLLECTION_NAME` do PostgreSQL com pgvector, ficando disponíveis para consulta semântica imediata.
4. O script é idempotente: re-executá-lo não duplica documentos na mesma coleção.
5. Erros de configuração (chave de API ausente, arquivo PDF não encontrado, banco inacessível) produzem mensagens claras e encerram com código de saída não-zero.

---

## Non-Goals

| Fora de escopo | Motivo |
|---|---|
| Interface web ou API REST para upload de PDF | É um CLI; UI é escopo de outra feature |
| Suporte a outros formatos (DOCX, HTML, TXT) | Requisito do desafio é exclusivamente PDF |
| Atualização incremental / diff de documentos já ingeridos | Complexidade desproporcional ao escopo do MBA |
| Tunagem automática de chunk size / overlap | Parâmetros são definidos nos requisitos do desafio |
| Monitoramento ou telemetria do processo de ingestão | Fora do escopo do MVP |

---

## User Stories

### Persona: Desenvolvedor / Avaliador do desafio MBA

- **US-01** — Como desenvolvedor, quero executar `python src/ingest.py` e ter o PDF inteiro indexado no pgvector, para que as queries semânticas subsequentes tenham contexto.
- **US-02** — Como desenvolvedor, quero que o script leia `PDF_PATH` do `.env`, para não precisar alterar código ao trocar o documento.
- **US-03** — Como desenvolvedor, quero poder usar tanto Google Generative AI quanto OpenAI como provedor de embeddings, para ter flexibilidade conforme a chave de API disponível.
- **US-04** — Como desenvolvedor, quero que o script informe quantos chunks foram gerados e confirmados no banco, para ter visibilidade do processo.
- **US-05** — Como desenvolvedor, quero que uma mensagem de erro clara seja exibida se `PDF_PATH` não existir ou se a conexão com o banco falhar, para diagnosticar problemas rapidamente.

---

## Requirements

### Must-Have (P0)

| ID | Requisito | Critério de Aceite |
|---|---|---|
| R01 | Carregar PDF via `PyPDFLoader` usando `PDF_PATH` | Dado um PDF válido em `PDF_PATH`, quando `ingest_pdf()` é chamado, então todos os documentos/páginas são carregados sem erro |
| R02 | Dividir texto em chunks de 1 000 chars / overlap 150 | Dado o texto extraído, quando o splitter é aplicado, então nenhum chunk excede 1 000 caracteres e chunks consecutivos compartilham 150 caracteres de sobreposição |
| R03 | Gerar embeddings com o provedor configurado (Google ou OpenAI) | Dado pelo menos uma `*_API_KEY` no `.env`, quando os chunks são processados, então cada chunk recebe um vetor de embedding sem erro de autenticação |
| R04 | Persistir vetores no pgvector via `PGVector` | Dado o banco acessível com a extensão `vector` instalada, quando `add_documents()` é chamado, então os vetores aparecem na tabela da coleção `PG_VECTOR_COLLECTION_NAME` |
| R05 | Ler configuração exclusivamente de variáveis de ambiente | O script não contém credenciais ou paths hard-coded; todas as configurações vêm do `.env` via `python-dotenv` |
| R06 | Validar presença de `PDF_PATH` antes de tentar abrir o arquivo | Se `PDF_PATH` não estiver definido ou o arquivo não existir, o script exibe mensagem de erro e encerra com `sys.exit(1)` |

### Nice-to-Have (P1)

| ID | Requisito | Critério de Aceite |
|---|---|---|
| R07 | Log de progresso: número de páginas carregadas e chunks gerados | Após o split, o script imprime `"X páginas carregadas, Y chunks gerados"` |
| R08 | Confirmação de sucesso com total de vetores inseridos | Após `add_documents`, o script imprime `"Ingestão concluída: Y vetores armazenados em '<coleção>'"` |
| R09 | Seleção automática de provedor: preferir Google se ambas as chaves estiverem presentes | Lógica de fallback documentada e testável via variáveis de ambiente |

### Future Considerations (P2)

- Suporte a ingestão de múltiplos PDFs em batch (lista de paths ou diretório).
- Verificação de hash do arquivo para evitar re-ingestão de documentos idênticos.
- Metadata enrichment: armazenar nome do arquivo, número de página e data de ingestão como metadados do chunk.

---

## Success Metrics

| Indicador | Meta | Como medir |
|---|---|---|
| Taxa de execução bem-sucedida | 100 % em PDFs válidos com `.env` correto | Execução manual / CI |
| Chunks gerados para PDF de referência do desafio | Valor estável e reprodutível entre execuções | Comparar contagem entre duas execuções com o mesmo PDF |
| Tempo de ingestão (PDF ~50 páginas) | < 60 segundos | `time python src/ingest.py` |
| Zero vetores duplicados após re-execução | Contagem na tabela não cresce na segunda execução | `SELECT count(*) FROM langchain_pg_embedding WHERE collection_id = ...` |

---

## Open Questions

| # | Questão | Responsável | Bloqueante? |
|---|---|---|---|
| Q1 | A idempotência deve deletar e re-inserir (replace) ou deve ser um no-op se a coleção já existir? | Desenvolvedor | Sim — impacta implementação de R04 |
| Q2 | O `RecursiveCharacterTextSplitter` é suficiente ou deve-se usar `CharacterTextSplitter`? O requisito menciona "chunks de 1 000 caracteres" sem especificar o separador | Desenvolvedor / Professor | Não — default `Recursive` é mais robusto |
| Q3 | Qual PDF será usado como documento de referência para o desafio? | Professor / Enunciado | Não — o script deve funcionar com qualquer PDF |

---

## Timeline Considerations

- Feature unblocks **F02 (Busca Semântica)** e **F03 (Chat RAG)** — deve ser a primeira entrega.
- Sem dependências externas além do ambiente Docker já configurado (`docker-compose up -d`).
