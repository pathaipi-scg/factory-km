
# LLM Wiki Design

Version: 1.0

This document defines the LLM Wiki subsystem.

LLM Wiki is the knowledge synthesis layer of Factory-KM.

---

# 1. Purpose

PageIndex retrieves documents.

LLM Wiki understands documents.

These are different responsibilities.

---

# 2. Responsibilities

LLM Wiki is responsible for

Cross-document understanding

Knowledge synthesis

Overview generation

Relationship discovery

Concept explanation

LLM Wiki is NOT responsible for

Semantic retrieval

OCR

Embedding

Dictionary

---

# 3. Position

Question

↓

Dictionary

↓

PageIndex

↓

Relevant Markdown

↓

LLM Wiki

↓

Azure GPT

↓

Answer

---

# 4. Knowledge Sources

LLM Wiki reads

KM Detail

KM Summary

Dictionary

Future

Knowledge Graph

---

# 5. Wiki Articles

Each engineering concept owns one Wiki article.

Examples

Roller

Mortar

Twin Loader

Hydraulic Pump

Inverter

---

# 6. Article Structure

Overview

Purpose

How it works

Related equipment

Common failures

Troubleshooting

Related alarms

Related documents

Related slides

Related dictionary entries

---

# 7. Incremental Update

New Markdown

↓

Update only affected Wiki articles

Never rebuild the entire Wiki.

---

# 8. Relationship Discovery

LLM Wiki may discover

Equipment

↓

Process

↓

Alarm

↓

Troubleshooting

↓

Maintenance

These relationships improve future answers.

---

# 9. Future Knowledge Graph

Future

Roller

↓

uses

↓

Bearing

↓

connected_to

↓

Motor

↓

monitored_by

↓

Current Sensor

Wiki should be compatible with a future graph database.

---

# 10. AI Agent Rules

LLM Wiki

≠

PageIndex

LLM Wiki

≠

Dictionary

Do not merge responsibilities.

---

# 11. Design Principles

Incremental

Traceable

Cross-document

Human readable

Version controlled

Knowledge preserving

Explain instead of retrieving.

---

# 12. Future

Automatic article updates

Relationship extraction

Failure pattern discovery

Maintenance recommendations

Cross-machine comparison

Cross-process knowledge

Knowledge graph generation

Conversation memory integration


