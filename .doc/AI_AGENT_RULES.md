
# AI Agent Rules

Before making any architectural decision:

1. Check existing documentation.
2. Reuse existing architecture whenever possible.
3. Do not introduce new subsystems without justification.
4. If a design change is required:
   - update the design document first,
   - then implement the code.

Version: 1.0

This document defines the operating rules for AI agents working on the
Factory-KM project.

These rules apply to all AI coding assistants.

Examples

- Codex
- Claude Code
- ChatGPT
- Future AI Agents

This document should be read BEFORE modifying any code.

---

# 1. Read Order

Always read documents in this order.

1.

FACTORY_KM_PACKAGE_SPEC.md

↓

2.

SYSTEM_ARCHITECTURE.md

↓

3.

Read only the design document related to the current task.

Examples

PageIndex

↓

PAGEINDEX_DESIGN.md

Dictionary

↓

DICTIONARY_DESIGN.md

LLM Wiki

↓

LLM_WIKI_DESIGN.md

Do not read unnecessary specifications.

---

# 2. Single Source of Truth

The Markdown specifications inside

.doc

are the authoritative design.

If implementation conflicts with these specifications

Follow the specifications

unless explicitly instructed otherwise.

Never invent new architecture.

---

# 3. Scope

Modify only the components required for the current task.

Do not refactor unrelated systems.

Examples

If fixing PageIndex

Do not modify Dictionary.

If improving Dictionary

Do not modify Training.

Keep component boundaries clear.

---

# 4. Token Optimization

Always minimize token usage.

Never inspect the whole KM Vault.

Never recursively read every Markdown.

Never inspect PNG files.

Never OCR images.

Never inspect Office documents.

Use one reference package unless comparison is explicitly required.

---

# 5. Factory KM Structure

Remember

Office Documents

↓

Training

↓

Markdown

↓

PageIndex

↓

Search

Original engineering documents are never indexed.

Images are never indexed.

Only trained Markdown is indexed.

---

# 6. Traceability

Always preserve

Source File

↓

Markdown

↓

Slide

↓

Original Image

↓

Answer

Every answer should be traceable back to its engineering source.

Never remove traceability.

---

# 7. Incremental Processing

Factory-KM is incremental.

Never rebuild everything unless explicitly instructed.

Prefer

New

↓

Index

Changed

↓

Reindex

Deleted

↓

Remove

Leave everything else untouched.

---

# 8. Recovery

Recovery

≠

Indexing

Recovery

≠

Rebuild

Recovery only restores identity and consistency.

Never call Azure during recovery.

---

# 9. Dictionary

Dictionary is independent.

Responsibilities

Factory terminology

Synonyms

Canonical words

Query expansion

Dictionary is not PageIndex.

---

# 10. LLM Wiki

LLM Wiki is independent.

Responsibilities

Knowledge synthesis

Cross-document understanding

Relationship discovery

LLM Wiki is not retrieval.

---

# 11. PageIndex

Responsibilities

Semantic retrieval

Workspace

Manifest

Incremental indexing

Recovery

Resume

Do not add unrelated responsibilities.

---

# 12. Safety Rules

Never delete user knowledge automatically.

Never delete Vault contents.

Never overwrite original engineering documents.

Never destroy traceability.

Never remove metadata.

When uncertain

Stop

Explain

Ask.

---

# 13. Coding Rules

Prefer

Small changes

↓

Verification

↓

Commit

Avoid

Large refactors

without approval.

---

# 14. Testing Rules

After every modification

Run only the tests required.

Avoid expensive validation unless requested.

Do not perform unnecessary indexing.

Do not perform unnecessary Azure calls.

---

# 15. Documentation

Whenever architecture changes

Update the corresponding specification first.

Architecture

↓

Specification

↓

Implementation

Not the other way around.

---

# 16. Design Principles

Factory-KM follows these principles.

Single Responsibility

Incremental Processing

Traceability

Human Maintainability

Deterministic Processing

Workspace Independence

Minimal Token Usage

Factory Terminology First

Preserve Original Engineering Documents

These principles should never be violated.

---

# 17. Expected Workflow

Read Specifications

↓

Understand Scope

↓

Modify Small Area

↓

Run Tests

↓

Review

↓

Commit

↓

Update Documentation (if architecture changed)

This workflow should be followed for all future Factory-KM development.


