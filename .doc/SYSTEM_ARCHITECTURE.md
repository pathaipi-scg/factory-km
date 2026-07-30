
# Factory KM System Architecture

Version: 1.0

This document describes the overall architecture of Factory-KM.

This is the high-level design.

Detailed implementation is described in individual specifications.

---

# 1. Goal

Factory-KM is an AI-powered engineering knowledge system.

The objectives are:

- Preserve engineering knowledge
- Search quickly
- Answer naturally
- Show original source
- Learn factory terminology
- Continuously grow without rebuilding the whole system

---

# 2. High Level Architecture

User

↓

Dictionary Resolver

↓

Knowledge Router

↓

PageIndex Search

↓

LLM Wiki (future)

↓

Azure OpenAI

↓

Answer

↓

Optional

Original Slide Image

---

# 3. Knowledge Pipeline

Engineering Document

↓

Training

↓

Markdown

↓

PageIndex

↓

Search

↓

Answer

Only trained Markdown enters PageIndex.

Original Office files never enter PageIndex.

---

# 4. Components

## 4.1 Training

Responsible for

- Office conversion
- OCR / Vision
- Markdown generation
- Summary generation

Outputs

KM_xxxxx.md

KM_xxxxx_summary.md

---

## 4.2 Vault

Stores

Original documents

Markdown

Images

Dictionary

Configuration

The Vault is the permanent knowledge repository.

---

## 4.3 PageIndex

Responsible for

Fast retrieval

Semantic search

Context retrieval

Workspace management

Incremental indexing

PageIndex never indexes Office or Images directly.

---

## 4.4 Dictionary

Responsible for

Factory terminology

Synonyms

Aliases

Canonical words

Operator vocabulary

Dictionary is independent from PageIndex.

---

## 4.5 LLM Wiki

Future component.

Responsible for

Knowledge synthesis

Cross-document understanding

Relationship generation

Overview articles

LLM Wiki does not replace PageIndex.

---

## 4.6 Azure OpenAI

Responsible for

Final reasoning

Answer generation

Context understanding

Never used for indexing Office documents directly.

---

# 5. Search Flow

User Question

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

# 6. Source Traceability

Every answer should preserve

Source document

↓

Slide

↓

Original image

↓

Original Office document

Every answer should be traceable.

---

# 7. Incremental Growth

New document

↓

Training

↓

Markdown

↓

PageIndex

↓

Immediately searchable

Existing documents are not rebuilt.

---

# 8. AI Learning

Factory-KM grows in three independent ways.

Knowledge

↓

New Markdown

Vocabulary

↓

Dictionary

Understanding

↓

LLM Wiki

These systems evolve independently.

---

# 9. Future Components

Planned

PageIndex Sync Manager

Dictionary Trainer

LLM Wiki Builder

Knowledge Graph

Automatic Document Versioning

Conversation Memory

---

# 10. AI Agent Rules

Always understand the architecture before modifying code.

Do not merge independent components.

Current separation is intentional.

Training

≠

PageIndex

≠

Dictionary

≠

LLM Wiki

≠

Azure GPT

Each component has a single responsibility.

---

# 11. Design Principles

Single Responsibility

Incremental Processing

Traceability

Minimal Token Usage

Human Maintainability

Factory terminology first

Source preservation

Never destroy original engineering documents.

---

# 12. Architecture Summary

Original Office

↓

Training

↓

Markdown

↓

PageIndex

↓

Dictionary Expansion

↓

Azure GPT

↓

Answer

↓

Original Slide (optional)

This architecture is considered the canonical Factory-KM design.

