# Training Pipeline Design

Version: 1.0

This document defines the Factory-KM knowledge training pipeline.

Training is responsible for converting engineering documents into searchable
knowledge.

Training is independent from PageIndex.

---

# 1. Purpose

The Training Pipeline converts engineering documents into structured Markdown.

The generated Markdown becomes the permanent knowledge stored in Factory-KM.

Only successfully trained Markdown is searchable.

---

# 2. Supported Input

Training accepts engineering documents such as

- Microsoft PowerPoint (.ppt)
- Microsoft PowerPoint (.pptx)

- Microsoft Word (.doc)
- Microsoft Word (.docx)

- Microsoft Excel (.xls)
- Microsoft Excel (.xlsx)

- PDF (.pdf)

Future versions may support

- Images
- CAD drawings
- Video
- Audio

---

# 3. High Level Pipeline

Engineering Document

↓

Extract Pages

↓

Generate Page Images

↓

Vision Analysis

↓

Slide Markdown

↓

Document Markdown

↓

Summary Markdown

↓

Vault

↓

PageIndex

---

# 4. Output Package

Every training job generates

Original Source

↓

KM_xxxxxxxxx.md

↓

KM_xxxxxxxxx_summary.md

↓

KM_xxxxxxxxx/

↓

Slide001.png

Slide002.png

...

The output package follows

FACTORY_KM_PACKAGE_SPEC.md

---

# 5. Page Images

Every page is converted into PNG.

Example

Slide001.png

Slide002.png

...

Purpose

- Preserve original appearance

- UI preview

- Human verification

- Future AI reference

PNG files are assets only.

They are never indexed.

---

# 6. Vision Analysis

Each page image is analyzed independently.

Output

Markdown

The Markdown should preserve

Headings

Tables

Lists

Engineering terminology

Warnings

Notes

Relationships

Do not preserve image pixels.

Preserve engineering meaning.

---

# 7. Detail Markdown

Generated file

KM_xxxxxxxxx.md

Contains

Metadata

↓

Page 1

↓

Page 2

↓

...

↓

Page N

Each page should preserve

Page Number

↓

Original Image

↓

Engineering Meaning

---

# 8. Summary Markdown

Generated file

KM_xxxxxxxxx_summary.md

Purpose

Fast overview.

Contains

Document summary

Major equipment

Major processes

Keywords

Common failures

Important alarms

Major troubleshooting topics

Summary is independent from Detail.

---

# 9. Metadata

Every generated Markdown should contain

KM_ID

Source_File

Target_Path

Asset_Folder

Status

Training_Status

Slide_Count

Created

Training_Date

Generator

Model

Prompt Version

Future metadata may be added.

---

# 10. Training Status

Possible values

Pending

Training

Completed

Failed

Retired

Only

Completed

or

Trained

documents may enter PageIndex.

---

# 11. Incremental Training

If a source document changes

Only retrain that document.

Never retrain the whole Vault.

Existing knowledge should remain untouched.

---

# 12. Re-Training

Operator may request

Retrain

↓

Generate new Markdown

↓

Replace active version

↓

Archive previous version

Traceability must always be preserved.

---

# 13. Failure Handling

Training failure should never destroy

Original source

Previous Markdown

Assets

Training should fail safely.

---

# 14. Versioning

Future versions may support

Version 1

↓

Version 2

↓

Version 3

Only one version is Active.

Older versions remain archived.

---

# 15. Integration

Training produces

Markdown

↓

PageIndex indexes

Markdown

↓

Dictionary expands

Question

↓

LLM Wiki synthesizes

Knowledge

Each subsystem has one responsibility.

---

# 16. AI Agent Rules

Training

≠

PageIndex

Training

≠

Dictionary

Training

≠

LLM Wiki

Never merge responsibilities.

---

# 17. Design Principles

Incremental

Recoverable

Traceable

Version Controlled

Human Verifiable

Preserve Original Engineering Documents

Never Destroy Existing Knowledge

---

# 18. Future

Planned

Batch Training

Background Training

Queue Management

Distributed Workers

Multiple Vision Models

Quality Scoring

Automatic Retraining

Training History

Training Dashboard

Training Metrics

---

# 19. Canonical Pipeline

Office

↓

Page Images

↓

Vision

↓

Detail Markdown

↓

Summary Markdown

↓

Vault

↓

PageIndex

↓

Search

↓

Answer

This pipeline is the canonical Factory-KM training architecture.
