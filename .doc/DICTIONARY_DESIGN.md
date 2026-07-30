
# Dictionary Design

Version: 1.0

This document defines the Factory-KM terminology system.

The Dictionary is responsible for understanding factory language.

It is completely independent from PageIndex.

---

# 1. Purpose

Factory operators often use different words for the same engineering concept.

Examples

Roller

↓

หัวรีด

↓

โรลเลอร์

↓

ลูกกลิ้ง

These words should lead to the same engineering knowledge.

---

# 2. Responsibilities

Dictionary is responsible for

- Synonyms
- Factory terminology
- Local vocabulary
- Canonical words
- Query expansion

Dictionary is NOT responsible for

- Semantic retrieval
- Embedding
- OCR
- Final reasoning

---

# 3. Position

User Question

↓

Dictionary Resolver

↓

Expanded Query

↓

PageIndex

↓

Azure GPT

Dictionary always runs before PageIndex.

---

# 4. Dictionary Storage

Dictionary is stored as Markdown.

Each engineering concept owns one Markdown file.

Example

Dictionary/

equipment/

roller.md

mixer.md

material/

cement.md

mortar.md

process/

coating.md

alarm/

motor_overload.md

---

# 5. Canonical Concept

Every dictionary entry has one canonical concept.

Example

Canonical

roller

Aliases

หัวรีด

โรลเลอร์

ลูกกลิ้ง

All aliases resolve to

roller

---

# 6. Relationships

Supported relationships

synonym

subtype

state

action

related

Examples

mortar

↓

ปูนเปียก

↓

synonym

mortar

↓

ปูนตาย

↓

state

mortar

↓

ทิ้งปูน

↓

action

---

# 7. Query Expansion

Question

หัวรีดไม่หมุน

↓

Canonical

roller

↓

Expanded Query

roller

หัวรีด

โรลเลอร์

ลูกกลิ้ง

Only then perform PageIndex search.

---

# 8. User Training

When Factory-KM cannot understand a word

The UI should offer

+ Dictionary

Operator may teach

Unknown Word

↓

Canonical Word

↓

Description

↓

Relation

↓

Save

---

# 9. Approval Workflow

Operator submission

↓

Pending

↓

Admin Review

↓

Approve

↓

Dictionary Active

Dictionary should never become active immediately.

---

# 10. Dictionary Sync

Changing Dictionary does NOT rebuild PageIndex.

Only reload

Terminology Resolver

Clear query cache if needed.

---

# 11. AI Agent Rules

Dictionary

≠

PageIndex

Dictionary

≠

LLM Wiki

Dictionary

≠

Training

Keep these systems independent.

---

# 12. Future

Future versions may support

Automatic synonym discovery

Usage frequency

Multiple languages

Department-specific terminology

Operator reputation

AI suggestions

---

# 13. Design Principles

Human editable

Markdown based

Version controlled

Incremental

Safe approval

Factory terminology first

Never hide the original canonical engineering term.

