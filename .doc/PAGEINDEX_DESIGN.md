
# PageIndex Design

Version: 1.0

This document defines how PageIndex is used inside Factory-KM.

It is the authoritative design for indexing, synchronization,
workspace management and document recovery.

---

# 1. Purpose

PageIndex is the retrieval engine of Factory-KM.

Its responsibilities are:

- Semantic retrieval
- Context retrieval
- Incremental indexing
- Workspace management
- Fast search

PageIndex is NOT responsible for

- OCR
- Office conversion
- Dictionary
- Final reasoning

---

# 2. Input

PageIndex receives ONLY trained Markdown.

Eligible

✓ KM_xxxxxxxxx.md

✓ KM_xxxxxxxxx_summary.md

Requirements

Status = Active

Training_Status = Trained

Everything else is rejected.

---

# 3. Never Index

Never send these files to PageIndex.

Office

- ppt
- pptx
- doc
- docx
- xls
- xlsx

Documents

- pdf

Images

- png
- jpg
- jpeg
- webp

Folders

- asset folders
- backup
- temp
- retired

System

- dictionary
- configuration
- logs

---

# 4. Document Types

PageIndex supports two document types.

## km_detail

Source

KM_xxxxxxxxx.md

Purpose

Detailed engineering knowledge.

Contains

- slide analyses
- source metadata
- equipment
- countermeasures
- process

---

## km_summary

Source

KM_xxxxxxxxx_summary.md

Purpose

Fast overview.

Contains

- document summary
- major topics
- high-level concepts

Summary is NOT a duplicate of Detail.

They are different document types.

---

# 5. Workspace

Workspace is the searchable PageIndex database.

Workspace stores

Document

↓

Nodes

↓

Embeddings

↓

Metadata

Workspace is independent from Vault.

---

# 6. Metadata

Each indexed document should preserve

KM_ID

Document_Type

Source_File

Target_Path

Asset_Folder

Status

Training_Status

Slide_Count

SHA256

Relative_Path

Workspace_Document_ID

These fields allow deterministic recovery.

---

# 7. Slide Mapping

Detail documents preserve

Slide Number

↓

Original PNG

Example

Slide 18

↓

KM_20260727_100714/Slide018.png

Images are not indexed.

Only the mapping is preserved.

The application may later display the original page.

---

# 8. Search Flow

Question

↓

Dictionary Resolver

↓

Expanded Query

↓

PageIndex

↓

Relevant Markdown

↓

Azure GPT

↓

Answer

↓

Optional Source Image

---

# 9. Incremental Index

Factory-KM never rebuilds the whole workspace.

Only changed Markdown is indexed.

New Markdown

↓

Index

Modified Markdown

↓

Reindex

Deleted Markdown

↓

Remove Document

Everything else remains untouched.

---

# 10. Sync

Sync compares

Vault Markdown

↓

Workspace

↓

Manifest

↓

Differences

↓

Update

Sync is deterministic.

---

# 11. Recovery

Recovery is used after

- interrupted indexing
- concurrent execution
- workspace corruption

Recovery never calls Azure.

Recovery never indexes documents.

Recovery only rebuilds identity.

---

# 12. Resume

Resume only indexes

pending

failed

missing

documents.

Completed documents must never be indexed again.

---

# 13. Duplicate Policy

Duplicate means

Two PageIndex documents

↓

Same Markdown

↓

Same SHA256

Summary and Detail are NOT duplicates.

---

# 14. Lock

Only one indexing process is allowed.

Requirements

Atomic lock

PID aware

Stale lock detection

Atomic state updates

Second runner exits immediately.

---

# 15. Manifest

Manifest stores

Relative Path

SHA256

Status

Workspace Document ID

Document Type

Index Time

Manifest is the source of truth for synchronization.

---

# 16. Workspace Independence

Vault

≠

Workspace

Deleting a workspace never deletes Vault.

Deleting Vault never modifies Workspace automatically.

Synchronization decides what changes.

---

# 17. Token Optimization

When working with PageIndex

Never inspect every KM package.

Never OCR PNG.

Never inspect Office files.

Inspect one reference package only.

Infer the remaining layout.

Only inspect more when explicitly required.

---

# 18. Future

Planned

Incremental Sync Manager

Workspace Versioning

Automatic Resume

Background Indexing

Workspace Migration

---

# 19. Phase 2 Local Read-Only Workspace

The production retrieval integration reads one pre-generated document from a
local filesystem workspace. It never generates or modifies index data.

Layout

```text
<PAGEINDEX_WORKSPACE_PATH>/
  documents/
    <PAGEINDEX_DOCUMENT_ID>/
      document.json
      structure.json
      pages.json
```

`document.json` is one JSON object containing PageIndex document metadata.
It must include a `doc_id` equal to `PAGEINDEX_DOCUMENT_ID`.

`structure.json` is one JSON array of tree nodes. Every node requires
`node_id`, `title`, `start_index`, and `end_index`. Optional fields are
`summary` and nested `nodes`.

`pages.json` is one JSON array ordered by source position. Every item requires
an integer `page` and string `content`. Node ranges refer to these `page`
values, inclusively.

Phase 2 supports one configured document only. Missing, invalid, or corrupt
workspace data falls back to Folder Search. Index generation, document
mapping, synchronization, manifests, recovery, and workspace mutation remain
out of scope.

This paragraph describes the implemented local read-only retrieval slice, not
the completion criteria for the overall Phase 2 product phase.

## Phase 2 Implementation Ordering

The product phase remains PageIndex. Its immediate prerequisite is a Manifest
Domain that supplies durable logical document/version identity and lifecycle
state.

Required sequence: Manifest Domain, PageIndex generation/discovery,
incremental sync/state transitions, recovery/resume/locking, Dictionary, then
LLM Wiki.

PageIndex generation must not invent a private second manifest. Manifest
persistence uses the central Factory-KM MSSQL database under the dedicated
`manifest` schema. The Vault remains authoritative content storage and the
workspace remains derived/rebuildable state. Absolute Windows paths are not
document identity.

## Manifest-Driven Discovery Slice

The discovery service is a workspace-independent planning layer. It reads only
active trained Markdown from the Manifest and classifies work as new/changed,
failed retry, pending resume, or missing workspace mapping.

Preparing work changes new, failed, and missing-mapping records to `pending`
through the Manifest repository and its rowversion concurrency check. Existing
pending records are resumed without incrementing their attempt count again.
Retired, untrained, original-source, and already mapped indexed records are not
scheduled.

An `indexed` record with no workspace mapping is deliberately representable as
recoverable inconsistent state. Discovery schedules it instead of rejecting or
silently treating it as complete.

This slice does not read Vault content, generate PageIndex files, call Azure,
or require a live MSSQL connection. Workspace generation remains the next
separate slice.

---

# 20. AI Agent Rules

Before modifying PageIndex

Read

FACTORY_KM_PACKAGE_SPEC.md

Then

Read

PAGEINDEX_DESIGN.md

Do not assume anything outside these specifications.

---

# 21. Design Principles

Incremental

Deterministic

Recoverable

Traceable

Token Efficient

Workspace Independent

These principles must always be preserved.
