
# Factory KM Package Specification

Version: 1.0

This document defines the standard Factory-KM package layout.

This specification must be followed by all indexing, search, synchronization,
training and maintenance tools.

---

# 1. Purpose

Factory-KM separates:

- Original engineering documents
- Trained knowledge
- UI assets

Only trained knowledge is searchable by PageIndex.

---

# 2. Standard Package Layout

Example

KM\Vault\Packing\Trouble_Shooting\

├── Troubleshooting Packer SCGR-CB 090726.xlsx
├── KM_20260727_100714.md
├── KM_20260727_100714_summary.md
└── KM_20260727_100714\
    ├── Slide001.png
    ├── Slide002.png
    ├── ...
    └── Slide038.png

Every KM package follows this structure.

---

# 3. Package Components

## 3.1 Original Source

Examples

- ppt
- pptx
- doc
- docx
- xls
- xlsx
- pdf

Purpose

- Original engineering document
- Traceability
- Re-training

These files MUST NOT be indexed.

---

## 3.2 Detail Markdown

Example

KM_20260727_100714.md

Contains

- KM metadata
- Complete slide analyses
- References to page images
- Source information

This IS searchable.

PageIndex document_type

km_detail

---

## 3.3 Summary Markdown

Example

KM_20260727_100714_summary.md

Contains

- Whole document summary
- High-level topics
- Fast retrieval overview

This IS searchable.

PageIndex document_type

km_summary

---

## 3.4 Asset Folder

Example

KM_20260727_100714/

Contains

Slide001.png
Slide002.png
...

Purpose

- UI preview
- Source evidence
- Show original page

Images MUST NOT be indexed.

Images MUST NOT be OCR'd during indexing.

Images MUST NOT be parsed unless explicitly requested.

---

# 4. PageIndex Eligibility

Eligible

✓ KM_xxxxxxxxx.md

✓ KM_xxxxxxxxx_summary.md

When

Status = Active

Training_Status = Trained

---

Not Eligible

Office files

PDF

PNG

JPG

Images

Dictionary

Backup

Temp

Retired

Inactive

Pending

Failed

System Markdown

Configuration Markdown

---

# 5. Metadata

Every searchable Markdown should contain metadata similar to

KM_ID

Source_File

Target_Path

Asset_Folder

Status

Training_Status

Slide_Count

Created

Training_Date

PageIndex may use this metadata.

---

# 6. Asset Relationship

Every detail Markdown owns one asset folder.

Example

KM_20260727_100714.md

↓

Asset_Folder

↓

KM_20260727_100714/

↓

Slide001.png

Slide002.png

...

PageIndex should preserve

Slide Number

↓

Asset Path

Example

Slide 18

↓

KM_20260727_100714/Slide018.png

The application can later display the original page image.

---

# 7. Search Model

User Question

↓

Dictionary Resolver

↓

PageIndex

↓

LLM

↓

Answer

↓

Optional UI

Show original slide image

---

# 8. Token Optimization

When modifying Factory-KM

DO NOT inspect the entire Vault.

DO NOT recursively read all Markdown.

DO NOT inspect PNG files.

DO NOT OCR images.

Use ONE package as the reference implementation.

Infer the remaining package layout from this specification.

Only inspect additional packages when explicitly requested.

---

# 9. Sync Model

Office/PDF

↓

Training

↓

Detail Markdown

↓

Summary Markdown

↓

PageIndex

↓

Search

PageIndex never indexes Office or Images directly.

---

# 10. Dictionary

Dictionary is a completely separate subsystem.

It is NOT part of PageIndex indexing.

Dictionary Markdown will later be consumed by

Terminology Resolver

Example

Dictionary

↓

Synonym

↓

Canonical Term

↓

PageIndex Search

---

# 11. Future Extensions

Future metadata may include

Index_Status

Index_Date

PageIndex_Document_ID

Workspace_ID

Version

These fields are optional.

---

# 12. Rules For AI Agents

When working on Factory-KM

DO

✓ Read this specification first

✓ Treat this as the canonical package layout

✓ Index only eligible Markdown

✓ Preserve source traceability

✓ Preserve slide-to-image mapping

DON'T

✗ Index Office files

✗ Index PDFs

✗ Index PNG files

✗ OCR images during indexing

✗ Scan the whole Vault unnecessarily

✗ Assume every Markdown is searchable

Always minimize token usage.