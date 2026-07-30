
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

# 19. AI Agent Rules

Before modifying PageIndex

Read

FACTORY_KM_PACKAGE_SPEC.md

Then

Read

PAGEINDEX_DESIGN.md

Do not assume anything outside these specifications.

---

# 20. Design Principles

Incremental

Deterministic

Recoverable

Traceable

Token Efficient

Workspace Independent

These principles must always be preserved.

