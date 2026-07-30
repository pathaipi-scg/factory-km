# Factory-KM Changelog

Version: 1.0

This document records important architectural decisions and project milestones.

It is NOT a Git commit history.

It records why important decisions were made.

---

# 2026-07-30

## Documentation

Added

- AI_AGENT_RULES.md
- SYSTEM_ARCHITECTURE.md
- FACTORY_KM_PACKAGE_SPEC.md
- TRAINING_PIPELINE_DESIGN.md
- PAGEINDEX_DESIGN.md
- DICTIONARY_DESIGN.md
- LLM_WIKI_DESIGN.md
- ROADMAP.md

Factory-KM now has a formal architecture specification.

---

## Package Structure

Decision

Factory-KM packages are standardized.

Each package consists of

Original Office Document

↓

Detail Markdown

↓

Summary Markdown

↓

Asset Folder

Original Office documents are never indexed.

---

## PageIndex

Decision

PageIndex indexes only

- KM_xxxxxxxxx.md
- KM_xxxxxxxxx_summary.md

Never

- Office
- PDF
- Images
- Dictionary

Reason

Avoid duplicated knowledge and unnecessary token usage.

---

## Asset Images

Decision

Slide images are stored as permanent assets.

Purpose

- UI display
- Human verification
- Source evidence

Images are never indexed.

Images are never OCR'd during indexing.

---

## Detail and Summary

Decision

Detail Markdown

and

Summary Markdown

are different document types.

They are NOT duplicates.

Reason

Summary supports fast retrieval.

Detail supports engineering answers.

---

## Dictionary

Decision

Dictionary is an independent subsystem.

Responsibilities

- Factory terminology
- Synonyms
- Canonical concepts
- Query expansion

Dictionary is not PageIndex.

---

## LLM Wiki

Decision

LLM Wiki is an independent subsystem.

Responsibilities

- Knowledge synthesis
- Cross-document understanding
- Relationship generation

LLM Wiki does not replace PageIndex.

---

## Recovery

Decision

Recovery

≠

Indexing

Recovery

≠

Rebuild

Recovery restores workspace identity only.

No Azure calls.

No indexing.

---

## Token Optimization

Decision

AI agents should inspect

One reference package only.

Never inspect the whole Vault.

Never inspect PNG assets.

Never OCR images unless explicitly requested.

Reason

Reduce cost.

Reduce latency.

Keep prompts deterministic.

---

## Current Project Phase

Roadmap

Phase 2

PageIndex

Current Tasks

- Recovery
- Resume
- Incremental Sync

Next Phase

Dictionary

---

## Future Decisions

Planned

- Dictionary Trainer UI
- Terminology Resolver
- LLM Wiki Builder
- Knowledge Graph
- AI Memory
- Multi Factory

---

# Changelog Rules

Record only

- Architectural decisions
- Design changes
- Major milestones
- Important project direction

Do NOT record

- Small bug fixes
- Formatting changes
- Refactoring
- Git commits

Git already stores implementation history.

This document stores engineering decisions.

# Factory-KM Changelog

Version: 1.0

This document records important engineering decisions,
architectural changes and major project milestones.

This is NOT a Git history.

Git records source code.

This document records engineering decisions.

---

# How to Write

Every entry should contain

Date

Decision

Reason

Impact

Status

Only record major engineering decisions.

---

# =======================================================================
# 2026-07-30
# =======================================================================

## Documentation Framework

### Decision

Created the Factory-KM engineering documentation framework.

Added

- AI_AGENT_RULES.md
- SYSTEM_ARCHITECTURE.md
- FACTORY_KM_PACKAGE_SPEC.md
- TRAINING_PIPELINE_DESIGN.md
- PAGEINDEX_DESIGN.md
- DICTIONARY_DESIGN.md
- LLM_WIKI_DESIGN.md
- ROADMAP.md

### Reason

Reduce repeated explanations.

Provide a single source of truth for all AI coding agents.

### Impact

Entire project.

### Status

Implemented

---

## Standard KM Package

### Decision

Every trained document follows a standard package structure.

Office Document

↓

Detail Markdown

↓

Summary Markdown

↓

Asset Folder

### Reason

Provide deterministic structure.

Improve synchronization.

Simplify future maintenance.

### Impact

Training

Vault

PageIndex

### Status

Implemented

---

## PageIndex Eligibility

### Decision

Only trained Markdown is searchable.

Eligible

- KM_xxxxxxxxx.md
- KM_xxxxxxxxx_summary.md

Rejected

- Office
- PDF
- Images
- Dictionary

### Reason

Avoid duplicate knowledge.

Reduce indexing cost.

Reduce Azure usage.

### Impact

Training

PageIndex

Sync

### Status

Implemented

---

## Detail vs Summary

### Decision

Detail Markdown

and

Summary Markdown

are different document types.

They are NOT duplicates.

### Reason

Summary provides fast document retrieval.

Detail provides engineering context.

### Impact

PageIndex

Search

### Status

Implemented

---

## Asset Images

### Decision

PNG images remain permanent assets.

They are used only for

- UI
- Human verification
- Source evidence

Never indexed.

Never OCR'd during indexing.

### Reason

Preserve original engineering evidence.

Reduce unnecessary processing.

### Impact

Training

UI

PageIndex

### Status

Implemented

---

## Dictionary

### Decision

Dictionary is a separate subsystem.

Responsibilities

- Synonyms
- Canonical words
- Factory terminology
- Query expansion

### Reason

Operators rarely use official engineering terms.

### Impact

Search

PageIndex

Future UI

### Status

Design Completed

---

## LLM Wiki

### Decision

LLM Wiki is independent from PageIndex.

Responsibilities

- Knowledge synthesis
- Cross-document understanding
- Relationship generation

### Reason

Searching and understanding are different responsibilities.

### Impact

Future Knowledge System

### Status

Design Completed

---

## Recovery

### Decision

Recovery

≠

Indexing

Recovery

≠

Rebuild

Recovery restores workspace identity only.

### Reason

Prevent accidental Azure calls.

Prevent duplicate indexing.

### Impact

PageIndex

### Status

Implemented

---

## Token Optimization

### Decision

AI agents should inspect only

ONE

reference package.

Never inspect

- entire Vault
- PNG
- Office

unless explicitly requested.

### Reason

Reduce token usage.

Reduce latency.

Improve deterministic behaviour.

### Impact

All AI Agents

### Status

Implemented

---

## AI Documentation

### Decision

All architecture discussions must become documentation.

Architecture

↓

Specification

↓

Implementation

### Reason

Architecture should not exist only inside conversations.

### Impact

Entire project.

### Status

Implemented

---

## Current Roadmap

Current Phase

Phase 2

PageIndex

Current Work

- Recovery
- Resume
- Incremental Sync

Next Phase

Phase 3

Dictionary

---

# =======================================================================
# Future Entries
# =======================================================================

Example

## YYYY-MM-DD

### Decision

...

### Reason

...

### Impact

...

### Status

Planned / In Progress / Implemented / Deprecated

