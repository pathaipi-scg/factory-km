
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

# Future Decisions

Continue assigning IDs

ADR-0008

ADR-0009

ADR-0010

...

Never modify historical decisions.

If a decision changes

Create a new ADR referencing the previous one.

The historical record must remain intact.

