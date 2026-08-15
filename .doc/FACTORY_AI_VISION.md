# Factory AI Vision

## Purpose

Factory-KM is envisioned as an AI-assisted factory knowledge and
problem-solving platform. It will evolve from retrieving approved engineering
knowledge toward helping people investigate live problems and convert reviewed
outcomes into better knowledge.

This document describes a long-term product direction. It is informational
only: it does not define implementation commitments, delivery dates, system
requirements, or changes to the current roadmap.

## Product Boundaries

Factory-KM should keep knowledge, operational evidence, and reasoning separate
while presenting them as one traceable user experience.

```text
Knowledge                         Factory evidence
-----------------------------     -----------------------------
Vault -> PageIndex -> LLM Wiki    MSSQL + InfluxDB + OPC UA
             \                         /
              +---- Factory-KM -------+
                         |
                         v
                   governed context
                         |
                         v
                        AI
                         |
                         v
              answer, evidence, action
```

The AI does not become a system of record and does not access production
systems without controlled Factory-KM services. Factory-KM remains responsible
for authorization, retrieval, context assembly, source traceability, audit,
and human approval boundaries.

## Component Responsibilities

### Vault

The Vault is the durable, human-governed knowledge repository. It preserves
original engineering documents, trained Markdown, images, metadata, and other
approved knowledge assets. It provides the source material and provenance from
which searchable and synthesized knowledge is derived. The Vault is not a
search index, operational database, or AI memory.

### PageIndex

PageIndex is the retrieval layer for trained knowledge. It incrementally
indexes eligible Markdown, locates passages relevant to a question, and
preserves mappings back to Vault sources. It optimizes discovery and context
selection; it does not replace the Vault, synthesize cross-document knowledge,
or make decisions.

### LLM Wiki

LLM Wiki is the curated synthesis layer. It turns approved source knowledge
into human-readable concept articles, relationships, overviews, and reusable
explanations across documents. Every synthesis should remain traceable to its
sources. LLM Wiki complements PageIndex: PageIndex retrieves evidence, while
LLM Wiki organizes and explains established knowledge.

### MSSQL

MSSQL is the system of record for structured factory and application facts
that require transactional consistency. Examples may include identities,
factory context, equipment references, document metadata, alarm mappings, and
approved workflow records. It supplies governed facts; it is not a semantic
knowledge store or time-series historian.

### InfluxDB

InfluxDB is the time-series history layer. It retains timestamped process and
machine observations for trends, event windows, comparisons, and anomaly
context. It explains what changed over time, but does not define authoritative
business entities or engineering knowledge.

### OPC UA

OPC UA is the controlled interface to current industrial signals, states, and
alarms. It provides the trigger and near-real-time context for assisted
investigation. In this vision, Factory-KM initially treats OPC UA as a
read-oriented evidence source. Any future control action would require a
separate safety, authorization, and operational design and is not implied by
this document.

### AI

AI interprets questions, reasons over the context Factory-KM supplies,
identifies missing evidence, explains findings, and proposes recommendations.
It should cite sources, express uncertainty, and ask for human input when the
evidence is incomplete. AI is not the authority for factory facts, knowledge
approval, or equipment control.

## Evolution Roadmap

### Phase I - Knowledge Retrieval

The first product stage makes approved engineering knowledge easy to find and
use. A user asks a question; Factory-KM retrieves relevant material from
PageIndex and LLM Wiki, with provenance back to the Vault, and provides a
bounded context package to AI for one answer.

```text
Question
   |
   v
PageIndex retrieval ----> LLM Wiki context
   |                            |
   +-------- Vault sources -----+
                |
                v
          Context package
                |
                v
               AI
                |
                v
       Answer with sources
```

The outcome is reliable knowledge retrieval, not factory-state analysis.
Operational databases and live signals are outside this phase.

### Phase II - Knowledge and Factory Facts

The second stage enriches retrieved knowledge with governed factory facts.
Factory-KM can combine document evidence with structured records from MSSQL
and historical measurements from InfluxDB. The AI still receives a single,
assembled context package and produces a single-pass response.

```text
Question or reported event
            |
      +-----+-----+
      |           |
      v           v
 Knowledge     Factory facts
 Vault         MSSQL
 PageIndex     InfluxDB
 LLM Wiki         |
      |           |
      +-----+-----+
            v
     Enriched context
            |
            v
           AI
            |
            v
  Evidence-based explanation
```

The product begins connecting what the factory knows with what the factory has
recorded, while preserving the authority and provenance of every source.

### Phase III - AI-Assisted Investigation

The third stage changes AI from a single-pass answer generator into a bounded
investigation partner. After reviewing initial context, AI may request
additional searches or queries through controlled Factory-KM tools. Factory-KM
authorizes and executes those requests, records the evidence gathered, and
returns it for another reasoning step.

```text
Initial context
      |
      v
 AI evaluates evidence
      |
      v
 Enough evidence? -- yes --> Finding with sources
      |
      no
      v
 Request approved tool query
      |
      v
 Factory-KM retrieves more evidence
      |
      +----------------------> AI evaluates evidence
```

Available evidence may include Vault sources, PageIndex results, LLM Wiki
articles, MSSQL facts, and InfluxDB history. If evidence remains insufficient,
the product asks an operator for observations rather than inventing an answer.
Investigation must have limits for time, query scope, cost, and iteration.

### Phase IV - Alarm Recommendation

The fourth stage makes investigation event-driven. A relevant OPC UA alarm or
state change can start a governed workflow. Factory-KM resolves the signal to
its factory context, gathers related knowledge and history, and presents an
explainable recommendation to an operator.

```text
OPC UA alarm
     |
     v
Alarm and asset mapping (MSSQL)
     |
     +------> Recent history (InfluxDB)
     |
     +------> Knowledge (PageIndex / LLM Wiki / Vault)
     |
     v
AI-assisted investigation
     |
     v
Recommendation + evidence + confidence
     |
     v
Operator decision and conversation
```

Recommendations remain advisory. Operators retain decision authority, and the
product records what evidence and knowledge supported each recommendation.

### Phase V - Closed Learning Loop

The fifth stage turns resolved work into reviewed organizational learning.
Operator feedback, investigation evidence, and observed outcomes become
knowledge candidates. Human owners review, edit, approve, or reject each
candidate before the Vault changes. Approved knowledge is then indexed by
PageIndex and may update affected LLM Wiki articles.

```text
Alarm / question / investigation
              |
              v
       Operator resolution
              |
              v
       Knowledge candidate
              |
              v
     Human review and approval
        |                 |
     reject              approve
        |                 |
      archive             v
                    Vault update
                         |
                  +------+------+
                  |             |
                  v             v
              PageIndex     LLM Wiki
                  |             |
                  +------+------+
                         v
              Better future context
```

"Closed" means the outcome can improve reviewed knowledge and later
recommendations. It does not mean autonomous self-training or unreviewed AI
changes. Versioning, provenance, review, rollback, and audit remain mandatory
product principles.

## Operational Knowledge Roadmap

Factory-KM is intended to preserve not only formal documentation but also the
operational experience generated during factory operation. The long-term
objective is to prevent knowledge loss caused by shift changes, personnel
rotation, and undocumented troubleshooting.

### Operational Knowledge Sources

Operational context may come from:

- Approved documentation (the Source of Truth)
- Alarm incidents
- Operator feedback
- Maintenance history
- Asset history
- Engineering investigations
- QA investigations
- Production incidents

These sources have different authority and review states. Factory-KM should
preserve those distinctions when retrieving, presenting, or learning from
them.

### Operational Memory

Operational memory accumulates from daily work. It may include:

- Alarm resolution history
- Equipment replacement history
- Sensor adjustment history
- Temporary workarounds
- Root cause investigations
- Photos taken during repairs
- Shift handover information

Operational memory does not replace the approved Source of Truth. It
complements official documentation by providing historical and situational
context for AI-assisted reasoning.

```text
Approved documentation                 Daily operational experience
(Source of Truth)                       (historical context)
        |                                       |
        |                         +-------------+-------------+
        |                         |             |             |
        |                      Alarms       Maintenance     Feedback
        |                         |             |             |
        +-------------------------+-------------+-------------+
                                  |
                                  v
                         Governed AI context
                                  |
                                  v
                    Explanation or recommendation

Authority is preserved: context does not become Source of Truth automatically.
```

### Shift Handover

Factory-KM should eventually produce AI-generated shift summaries from
traceable operational records. The experience should help incoming personnel
answer questions such as:

- What happened during the previous shift?
- Which alarms occurred?
- Which equipment was repaired?
- What work remains unfinished?
- Which alarms should be monitored today?

A shift summary is a generated operational view, not an authoritative record
by itself. It should identify its time window, sources, unresolved items, and
uncertainties so that operators can verify it.

```text
Alarms + work records + operator notes + maintenance and asset history
                              |
                              v
                    Shift-bounded context
                              |
                              v
                    AI-generated summary
                              |
                              v
       Events | Repairs | Open work | Risks to monitor
                              |
                              v
                      Incoming shift
```

### Continuous Learning

Operator feedback should initially remain separate from official
documentation. It remains searchable as historical evidence, including after
the Source of Truth is updated. This preserves the original operational record
and avoids silently turning an observation or workaround into approved
instruction.

When feedback identifies a durable improvement, document owners may review it
through the Phase V knowledge-candidate workflow. Only an approved change is
incorporated into the Source of Truth.

```text
Operator feedback --------------------> Searchable operational history
        |
        v
Knowledge candidate
        |
        v
Document-owner review
   |             |
 reject        approve
   |             |
   |             v
   |       Source of Truth update
   |             |
   +-------------+----> Historical feedback remains searchable
```

## End-State Experience

At maturity, Factory-KM helps an operator move through one traceable flow:

```text
Detect -> Understand -> Investigate -> Recommend -> Decide -> Learn
```

The enduring product promise is not that AI replaces engineering judgment. It
is that people can reach better-supported decisions faster, preserve what they
learn, and make that reviewed learning available the next time the factory
faces a similar problem.
