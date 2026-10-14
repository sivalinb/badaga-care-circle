# Illustrated user and system flows

[Home](../README.md) · [Architecture](architecture.md) · [AI and RAG](ai-and-rag.md) · [Evals](evaluations.md)

![Education, human review, check-in and family support flows](assets/workflows.svg)

The examples below use fictional records. Fixed warning guidance appears immediately; a queued reviewer is never an emergency response service.

## General education and optional drafts

```mermaid
flowchart TD
    Q[Question and selected language] --> A[Check demo actor, scope and length]
    A --> G{Fixed safety / privacy route}
    G -->|Current warning signs| E[Fixed emergency guidance; bypass AI]
    G -->|Medication or personal clinical request| C[Fixed boundary; optional clinical review request]
    G -->|Very high BP wording| U[Fixed prompt-attention guidance]
    G -->|Secret / injection request| B[Blocked]
    G -->|General education| R[Retrieve active source cards]
    R --> N{Evidence available?}
    N -->|No| X[Abstain]
    N -->|Yes| M{Chosen mode}
    M -->|Local| L[Linked source excerpts]
    M -->|Template| T[Labelled deterministic draft]
    M -->|OpenAI| K{Configured and cloud consent?}
    K -->|No| L
    K -->|Yes| O[Optional embeddings and structured draft]
    O --> V{Draft checks pass?}
    V -->|No / API failure| L
    V -->|Yes| H[Withhold draft in review queue]
    T --> H
    H --> P[Participant sees source excerpts and pending status]
```

The router is a conservative rule-based demo with limited wording coverage. It does not diagnose, prescribe or calculate cardiac-arrest risk. See [the evaluation limits](evaluations.md) and [clinical release gates](../ROADMAP.md).

## Human approval and release

```mermaid
sequenceDiagram
    actor Family as Household member
    participant Service as CareService
    participant Queue as SQLite reviews
    actor Reviewer as Demo clinical reviewer
    participant KB as Knowledge cards
    Family->>Service: Request template / consented AI draft
    Service->>Queue: Save draft, language, source IDs and versions as pending
    Service-->>Family: Show linked source excerpts and review ID
    Reviewer->>Service: Inspect review and add required notes
    Reviewer->>Service: Approve or reject education draft
    Service->>KB: On approval, verify versions and expiry
    Service->>Queue: Save decision and reviewed timestamp
    Family->>Service: Check review status
    Service->>Queue: Enforce household scope and approved status
    Service->>KB: Verify language, versions and expiry again
    Service-->>Family: Release approved cited text, or pending/rejected/stale status
```

Approving an education draft does not approve the underlying source corpus for clinical deployment. Existing drafts remain in their original language. Changing the interface language does not silently translate a reviewer-approved response.

Clinical review records use `followup` or `close`; education records use `approve` or `reject`. Closing a check-in review marks the linked check-in completed. The demo permits a reviewer to revise decisions and does not implement concurrent-review locking, reviewer assignment or overdue escalation.

## BP check-in

```mermaid
flowchart TD
    I[Selected household member, BP values and symptom choices] --> P[Check scope and member]
    P --> E{Current warning signs?}
    E -->|Yes| F[Show fixed emergency guidance before consent or saving]
    E -->|No| V[Validate number ranges / units]
    V --> R[Apply demo age / pregnancy / BP route]
    R --> C{Numbers confirmed and record consent?}
    C -->|No| N[Show relevant guidance; do not save]
    C -->|Yes| T[One transaction: check-in + review + audit]
    T --> H[Reviewer inspects fictional record]
    H --> O[Follow-up or completed state]
```

The demo flags systolic ≥180 **or** diastolic ≥120 for prompt attention. This conservative software boundary needs local clinical approval; it is not a diagnosis or a complete triage protocol. Every recorded check-in gets a review, including readings below that boundary. Saving a check-in does not book care or guarantee that a person has reviewed it.

## Share the care

```mermaid
stateDiagram-v2
    [*] --> requested: Scoped helper + valid due date + sharing consent
    requested --> accepted: Record acceptance
    accepted --> completed: Record completion
    completed --> [*]
```

Tasks support transport, bills, elder care and rest/time relief. The helper must be a fictional member of the selected household. The current role controls can record transitions; there is no verified helper identity or remote notification. Skipping directly from requested to completed, reverting a completed task or assigning a helper from another household is rejected.

A real programme must confirm that the helper agreed and the person receiving help benefited. Cancellation, reassignment, reminders and receipt confirmation are future workflow work.

## Family backup

```mermaid
flowchart LR
    A[Choose two distinct household adults] --> B[Write fictional contact plan, document locations and routines]
    B --> C[Length and secret-pattern check]
    C --> D[Save private scoped checklist]
    D --> E[Practise handover and record rehearsal]
```

The checklist stores document locations and routines, not passwords, government identifiers or account numbers. Pattern checks catch some unsafe entries, not every sensitive value. Volunteers cannot access the backup plan. The main programme outcome is that two willing adults can carry out the routines, not merely that a form was saved.

## Demo permissions

| Operation | Household member | Volunteer | Clinical reviewer |
|---|---|---|---|
| General education | Selected household | Selected household | Selected household |
| Tasks and transitions | Own selected household | Own selected household | Any selected household |
| Check-ins and private backup | Own selected household | Restricted | Any selected household |
| Review queue / decisions | Own education review status only; no decisions | Restricted | Queue and decisions |
| Traces / operational metrics | Restricted | Restricted | Available |

The backend applies these demo scopes even if a hidden UI control is called directly. The identity itself comes from unverified selectors, so these rules must not be treated as protection for real patient data.

## Language switching

English/Tamil labels, options, fixed messages, source excerpts and roadmap change through explicit translations. Eight permanent navigation labels remain bilingual. Context changes clear unsaved inputs; persisted records remain. Free-text notes and approved drafts keep their original language. Tamil wording still needs fluent-speaker and clinician approval; Tamil support is not Badaga-language support.
