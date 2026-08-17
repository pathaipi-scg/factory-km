
# Factory-KM Session Status

Version: 1.0

This document records the current working state of the project.

Unlike ROADMAP.md, this file represents the current checkpoint of development.

Unlike CHANGELOG.md, this file is updated continuously.

---

# Last Updated

2026-08-17

---

# Current Phase

Phase 2

PageIndex

---

# Current Objective

Implement the Engineering Document Extraction Foundation after the completed
Training Markdown hook. PageIndex workspace generation, Dictionary, and LLM
Wiki are paused while this cross-project integration slice is reviewed.

Focus on evidence-bearing Quotation/Manual drafts, canonical lookup, human
confirmation, and disabled-by-default controlled canonical execution.

Engineering Review Persistence and Confirmed Operation Command Foundation now
adds intended central MSSQL `engineering.*` migrations, immutable `EXR_`
snapshots, rowversion-protected `REV_` workflow state, and deterministic `CMD_`
commands that initially stopped at READY. No live migration was applied. Phase 1
executor code is now implemented behind the false-by-default write gate.

---

# Completed

## Documentation

- [x] AI_AGENT_RULES.md
- [x] SYSTEM_ARCHITECTURE.md
- [x] FACTORY_KM_PACKAGE_SPEC.md
- [x] TRAINING_PIPELINE_DESIGN.md
- [x] PAGEINDEX_DESIGN.md
- [x] DICTIONARY_DESIGN.md
- [x] LLM_WIKI_DESIGN.md
- [x] ROADMAP.md
- [x] CHANGELOG.md
- [x] DECISION_LOG.md
- [x] MANIFEST_DESIGN.md
- [x] Manifest Domain models and discovery contract
- [x] Central MSSQL `manifest` migrations and repository foundation
- [x] Manifest-driven PageIndex discovery/planning service

---

## Architecture

- [x] Documentation First workflow
- [x] Standard KM Package structure
- [x] Markdown as canonical knowledge
- [x] Detail / Summary document model
- [x] Asset image policy
- [x] Dictionary architecture
- [x] LLM Wiki architecture

## Training Migration

- [x] FastAPI Training migration core
- [x] Node to FastAPI Training gateway parity
- [x] Existing Node login/session behavior preserved
- [x] PPTX, XLSX, and PDF operator-path verification
- [x] Automated parity coverage for PPT, PPTX, XLS, XLSX, DOC, DOCX, and PDF

Verification gap

- DOC and DOCX real smoke testing is environment-blocked by active Word COM
  sessions. This is not a Training implementation blocker.

---

# Current Work

PageIndex prerequisite: Manifest Domain

- [x] Approve central MSSQL `manifest` persistence
- [x] Implement Manifest identity and lifecycle domain
- [x] Implement PageIndex discovery/planning
- [ ] Implement PageIndex workspace generation
- [ ] Implement incremental sync and state transitions
- [ ] Implement recovery, resume, and locking

---

# Next Phase

Phase 3

Dictionary

Planned

- Terminology Resolver
- Query Expansion
- Dictionary Manager
- Dictionary Trainer UI

---

# Not Started

- LLM Wiki
- Knowledge Graph
- Conversation Memory
- Multi Factory

---

# Important Rules

Always read before coding

1. AI_AGENT_RULES.md
2. SYSTEM_ARCHITECTURE.md
3. ROADMAP.md
4. Relevant design document

Documentation is the single source of truth.

If implementation conflicts with documentation,

follow the documentation.

---

# Current Architecture

Training

↓

Markdown

↓

PageIndex

↓

Search

↓

Azure GPT

↓

Answer

LLM Wiki is not implemented yet.

---

# Vault Rules

Index only

- KM_xxxxxxxxx.md
- KM_xxxxxxxxx_summary.md

Never index

- Office
- PDF
- PNG
- Asset Folder
- Dictionary

---

# Current Branch

main

---

# Next Session

Review the Engineering Document Extraction Foundation. The next persistence
and confirmed-canonical-write slice requires separate approval.

Do NOT begin Dictionary implementation until PageIndex is complete.

Manifest persistence uses the central Factory-KM MSSQL database and dedicated
`manifest` schema; do not substitute SQLite, filesystem JSON, or plant-specific
databases.

Do NOT select or implement Manifest persistence until its backend is approved.

---

# Notes

This file should always reflect the latest project state.

Update this document at the end of every engineering session.

Engineering Controlled Canonical Execution Phase 1 is implemented and awaits
review. READY commands now support dry-run and gated, allowlisted, leased serial
execution. Supplier/Contact/EPT master-data commands remain BLOCKED. No live
gate, migration, Vault write, Azure call, Kepware change, or OpcTagManager
mutation was used during implementation or testing.
