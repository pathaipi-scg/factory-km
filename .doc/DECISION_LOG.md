
# Factory-KM Decision Log

Version: 1.0

This document records major architectural decisions made during the
development of Factory-KM.

Unlike CHANGELOG.md, this document explains WHY a decision was made.

This document is the architectural memory of the project.

---

# Decision Record Template

Every decision should contain

Decision ID

Date

Status

Decision

Context

Options Considered

Decision

Consequences

Related Documents

---

# ===========================================================================
# ADR-0001
# ===========================================================================

Title

Use Markdown as the canonical engineering knowledge format.

Date

2026-07-30

Status

Accepted

---

## Context

Factory-KM needs a long-term knowledge format that is

- Human readable
- AI readable
- Version controlled
- Easy to review
- Easy to edit

The knowledge should survive AI model changes.

---

## Options Considered

Option A

SQL Database

Pros

- Fast query
- Structured

Cons

- Hard for humans to edit
- Poor Git support

---

Option B

JSON

Pros

- Structured

Cons

- Difficult to review
- Not pleasant to edit

---

Option C

Markdown

Pros

- Human readable
- AI friendly
- Git friendly
- Version controlled
- Easy diff
- Easy review

Cons

- Search requires indexing

---

## Decision

Markdown is the canonical knowledge format.

---

## Consequences

Training produces Markdown.

PageIndex indexes Markdown.

LLM Wiki reads Markdown.

Dictionary is Markdown.

Original Office documents remain unchanged.

---

## Related Documents

FACTORY_KM_PACKAGE_SPEC.md

TRAINING_PIPELINE_DESIGN.md

---

# ===========================================================================
# ADR-0002
# ===========================================================================

Title

Only trained Markdown is indexed.

Date

2026-07-30

Status

Accepted

---

## Context

The Vault stores

Office

Markdown

Images

Dictionary

System files

Not everything should enter PageIndex.

---

## Options Considered

Index everything

Pros

Simple

Cons

Duplicate knowledge

Waste Azure tokens

Waste storage

Slow indexing

---

Index trained Markdown only

Pros

Small index

Fast

Deterministic

Easy recovery

Cons

Requires eligibility rules

---

## Decision

PageIndex indexes only

KM_xxxxxxxxx.md

KM_xxxxxxxxx_summary.md

Status = Active

Training_Status = Trained

---

## Consequences

Office never indexed.

Images never indexed.

Dictionary never indexed.

---

## Related Documents

PAGEINDEX_DESIGN.md

FACTORY_KM_PACKAGE_SPEC.md

---

# ===========================================================================
# ADR-0003
# ===========================================================================

Title

Summary and Detail are different document types.

Date

2026-07-30

Status

Accepted

---

## Context

The project generates

Detail Markdown

Summary Markdown

Should they be merged?

---

## Options Considered

Merge

Pros

One document

Cons

Large context

Slow retrieval

Poor ranking

---

Separate

Pros

Fast overview

Small context

Better retrieval

Cons

Two documents

---

## Decision

Use

km_detail

and

km_summary

as separate document types.

---

## Consequences

Summary is not a duplicate.

Both are searchable.

---

## Related Documents

PAGEINDEX_DESIGN.md

---

# ===========================================================================
# ADR-0004
# ===========================================================================

Title

Keep Page Images outside PageIndex.

Date

2026-07-30

Status

Accepted

---

## Context

Training produces

Slide001.png

Slide002.png

...

Should images be indexed?

---

## Options Considered

Index images

Pros

Visual search

Cons

Expensive

Slow

Duplicate information

---

Keep as assets

Pros

Simple

Fast

Traceable

Cons

Need slide mapping

---

## Decision

Images remain assets only.

---

## Consequences

Images are never OCR'd during indexing.

Only slide mapping is stored.

UI may display images later.

---

## Related Documents

FACTORY_KM_PACKAGE_SPEC.md

TRAINING_PIPELINE_DESIGN.md

---

# ===========================================================================
# ADR-0005
# ===========================================================================

Title

Dictionary is independent from PageIndex.

Date

2026-07-30

Status

Accepted

---

## Context

Operators use factory language.

Engineering documents use official terminology.

These vocabularies differ.

---

## Decision

Dictionary performs

Synonym resolution

Canonical mapping

Query expansion

before PageIndex.

---

## Consequences

PageIndex remains simple.

Dictionary can evolve independently.

---

## Related Documents

DICTIONARY_DESIGN.md

SYSTEM_ARCHITECTURE.md

---

# ===========================================================================
# ADR-0006
# ===========================================================================

Title

LLM Wiki is a knowledge synthesis layer.

Date

2026-07-30

Status

Accepted

---

## Context

Searching

and

Understanding

are different problems.

---

## Decision

PageIndex retrieves.

LLM Wiki understands.

Azure GPT answers.

---

## Consequences

Responsibilities remain separated.

Future Knowledge Graph integration becomes easier.

---

## Related Documents

LLM_WIKI_DESIGN.md

SYSTEM_ARCHITECTURE.md

---

# ===========================================================================
# ADR-0007
# ===========================================================================

Title

Adopt Documentation-First Development.

Date

2026-07-30

Status

Accepted

---

## Context

Important architecture decisions were previously stored only inside AI conversations.

Future AI agents would lose this knowledge.

---

## Decision

Every architectural decision must be documented before implementation.

Workflow

Decision

↓

Specification

↓

Implementation

↓

Testing

---

## Consequences

Architecture becomes permanent.

Future AI agents understand project history.

Knowledge survives conversations.

---

## Related Documents

AI_AGENT_RULES.md

CHANGELOG.md

SYSTEM_ARCHITECTURE.md

---

# ===========================================================================
# ADR-0008
# ===========================================================================

Title

Make Manifest Domain the immediate prerequisite within PageIndex Phase 2.

Date

2026-08-17

Status

Accepted

## Context

PageIndex recovery, resume, incremental synchronization, and workspace mapping
require one durable source of document/version identity and lifecycle state.
The roadmap and status documents previously described the same phase using
different immediate priorities.

## Decision

Factory-KM remains in Phase 2 — PageIndex. Work proceeds in this order:

Manifest Domain, PageIndex generation/discovery, incremental sync/state
transitions, recovery/resume/locking, Dictionary, then LLM Wiki.

Manifest persistence uses the central Factory-KM MSSQL database in a dedicated
`manifest` schema, separate from `auth`. Factory/plant/process identities are
record metadata rather than separate Manifest databases. Factory-KM owns the
schema migrations. State changes use SQL transactions and SQL Server
`rowversion` optimistic concurrency.

The Vault remains authoritative for content and artifacts. PageIndex
workspaces are derived and rebuildable. Only relative/path-independent locators
may be stored. External ResourceId, SUP, CNT, EPT, KepwarePath, TaskId, and
future QUO identities remain logical references without cross-database foreign
keys.

## Consequences

PageIndex does not create a private competing manifest. Dictionary and LLM Wiki
remain downstream roadmap items. Manifest uniqueness and idempotency are
enforced in the central database while live content remains in the Vault.

## Related Documents

PAGEINDEX_DESIGN.md

NEXT_STEPS.md

PROJECT_STATUS.md

---

# ===========================================================================
# ADR-0010
# ===========================================================================

Title

Run engineering document extraction after successful Training and keep canonical engineering identity in OpcTagManager.

Date

2026-08-17

Status

Accepted

## Context

Factory-KM already produces traceable detail and summary Markdown. Quotations
and Manuals need evidence-bearing structured understanding without duplicating
conversion or canonical Supplier, Contact, Equipment/Part, and Resource
registries.

## Decision

Extraction consumes the successfully trained detail/summary pair and produces
a persistence-neutral human-review draft. Factory-KM calls OpcTagManager's
read-only candidate APIs over HTTP and preserves ambiguity. OpcTagManager owns
canonical identities and relationships. No canonical write occurs in the
foundation slice. PageIndex, Dictionary, LLM Wiki, live Manifest migration,
shared Auth, and KMVaultManager migration are not dependencies.

## Consequences

Evidence and source SHA/version information remain available for review and
reruns. Service/freight/commercial lines are not forced into EPT identities.
Confirmed canonical writes require a later, separately approved slice.

## Related Documents

ENGINEERING_DOCUMENT_EXTRACTION_DESIGN.md

FactoryKM_OpcTagManager_Integration_Context_20260817.md

---

# Future Decisions

## ADR-0011 - Central engineering review persistence and READY-only commands

Date: 2026-08-17

Status: Accepted

Factory-KM persists immutable extraction snapshots, mutable rowversion-protected
reviews, reviewer decisions, audit-compatible review events, and idempotent
confirmed-operation intents in the central MSSQL `engineering` schema. This is
separate from `auth` and `manifest`. Commands stop at READY; there is no command
worker or OpcTagManager mutation API in this phase. Candidate version metadata
is preserved when supplied, but OpcTagManager does not yet guarantee a canonical
revision token. Read-only Kepware Tag search is also an integration gap.

# Future Decisions

Continue assigning IDs

ADR-0009

ADR-0010

...

Never modify historical decisions.

## ADR-0012 - Controlled canonical execution with disabled-by-default dual gates

Execute only confirmed persisted commands through a fixed Phase 1 allowlist.
Factory-KM must pass `ENGINEERING_CANONICAL_WRITE_ENABLED`; OpcTagManager's
server gate remains independent. Compare reviewed and current canonical
revisions and verify exact active KepwarePath immediately before mutation.
Use atomic leases, serial dependency order, structured results, audit events,
and non-destructive retry. Resolve source bytes through logical `KM_` identity.
Supplier/Contact/EPT master-data mutation and shared Auth remain deferred.

## ADR-0012 - Controlled canonical execution with disabled-by-default dual gates

Execute only confirmed persisted commands through a fixed Phase 1 allowlist.
Factory-KM must pass `ENGINEERING_CANONICAL_WRITE_ENABLED`; OpcTagManager's
server gate remains independent. Compare reviewed and current canonical
revisions and verify exact active KepwarePath immediately before mutation.
Use atomic leases, serial dependency order, structured results, audit events,
and non-destructive retry. Resolve source bytes through logical `KM_` identity.
Supplier/Contact/EPT master-data mutation and shared Auth remain deferred.

If a decision changes

Create a new ADR referencing the previous one.

The historical record must remain intact.
