
ADR-001
Authentication
Node remains production until final cutover.

ADR-002
Authentication database
Central database = factory-km

ADR-003
Plant databases
SB11
SB12
CB
LP2
KK2

ADR-004
Each plant has independent

- Vault
- Chat
- PageIndex
- Dictionary
- Wiki

ADR-005
StableDocumentId is the canonical identity.

ADR-006
Filesystem path is never the document identity.

ADR-007
PageIndex document ID is disposable.

ADR-008
Factory-KM remains in product Phase 2 — PageIndex. Manifest Domain is the
immediate implementation prerequisite. The sequence is Manifest Domain,
PageIndex generation/discovery, incremental sync/state transitions,
recovery/resume/locking, Dictionary, then LLM Wiki.

ADR-009
Manifest identity must be logical and path-independent. A durable Manifest
persistence backend uses the central Factory-KM MSSQL database in a dedicated
`manifest` schema. The Vault remains authoritative content storage; PageIndex
workspaces are derived. Manifest records use transactions and SQL Server
rowversion concurrency. External logical identities have no cross-database
foreign keys.

ADR-010
Factory-KM owns engineering-document AI extraction and human review drafts
after successful Training Markdown generation. OpcTagManager remains the
canonical engineering identity and relationship owner. The foundation uses
only logical read-only HTTP candidate contracts; filesystem coupling and
canonical mutation are prohibited.
