# Working evidence and how to reproduce it

[Home](../README.md) · [Evaluations](evaluations.md) · [Observability](observability.md)

The README shows three direct screenshots of the live Gradio quality widgets: [evaluation](assets/evidence/live-evals.jpg), [redacted traces](assets/evidence/live-traces.jpg) and [operational metrics](assets/evidence/live-metrics.jpg). A [full-page capture](assets/evidence/live-quality-full.jpg) retains the app's surrounding context. These were browser captures, not recreated mockups. No numbers or labels were added to the pixels.

## What was actually exercised

The app was restarted with a fresh fictional database. Six UI requests were made and their visible responses checked:

| Scenario | Observed result | Trace status |
|---|---|---|
| Share caregiver responsibilities, local mode | Linked caregiver source summary | `source_excerpts` |
| Current chest pain in a fictional adult | Fixed warning guidance, optional AI bypassed | `fixed_guidance` |
| Stop BP tablets in a fictional example | Fixed prescriber boundary | `fixed_guidance` |
| “How does quantum computing work?” | No evidence; abstention | `no_evidence` |
| Caregiver question in template mode | Draft withheld for human review | `pending_review` |
| Same question in OpenAI mode without cloud consent | Labelled local fallback; no provider call | `local_fallback` |

The [RAG screen](assets/evidence/live-rag.jpg) and [off-topic screen](assets/evidence/live-abstention.jpg) show two of those actual responses. The pending-review check demonstrates withholding, not a new clinical approval or a complete human-review cycle. Eleven earlier browser checks, recorded in the build report, include a simulated reviewer approval and household release.

## Values behind the images

The [live capture JSON](evidence/live-demo.json) contains the complete result copied from each visible widget, capture time, scenario list, and SHA-256 hashes of the app/knowledge files used. Metadata strings in the trace records are preserved as returned by the UI. It contains no raw question text, BP reading or household key in its traces.

The evaluation result is **46/46**, with no critical failures. The six-request metric window shows one source answer, two fixed responses, one abstention, one pending template and one consent fallback. Input/output tokens are zero because no external AI processing occurred. Latency is a small local-session measurement and not a service-level or clinical benchmark.

The `app_source_hashes` identify the captured implementation independently of later README edits. Compare them with the files in the repository to check which app version produced the evidence. The complete UI evaluation report is also saved as [`evaluation_report.json`](../evaluation_report.json).

## Reproduce the software checks

```bash
python -m pip install -r requirements.lock
python -m pytest
python -m badaga_care eval --output artifacts/evaluation.json
python scripts/check_docs.py
```

This revision has **53 passing Python tests and 46 local evaluation cases**. GitHub Actions repeats those checks on each push/PR and attaches synthetic evaluation/JUnit reports. The [workflow and run history](https://github.com/sivalinb/badaga-care-circle/actions/workflows/ci.yml) show their individual step results. The README badge tracks the latest run; run URLs and artifacts in the history are the fixed records for each commit.

## Reproduce the UI capture

1. Start the app with a new `CARE_DATA_DIR` for fictional data and choose English, household A and the household-member demo role.
2. Use **Guide** to submit the six scenarios above. Leave external-processing consent unchecked; this capture needs no API key.
3. Switch to the demo clinical role, then **Quality / தரம்**. Click **Run local evaluation suite** and wait for its result.
4. Expand **Recent redacted traces** and **Operational metrics**. Refresh their contents if needed. Use the widgets' **Copy** controls to export the actual JSON.
5. Take browser screenshots of the panels and one full-page screenshot. Review pixels and exported values before publication; use only fictional inputs.

The capture used the existing browser size. Only screenshot rectangles were cropped to the panels; page data, styling and displayed values were not edited for the pictures. Different machines and request histories will produce different timestamps, trace IDs and latencies.

## Verification finding and limits

The first exploratory off-topic check exposed generic-word overlap in retrieval. It was fixed by excluding common auxiliary verbs from topic tokens, then verified with a new critical case, a workflow test and the new live screenshot. The three formerly matched cards are no longer returned for that question. Broader retrieval and language quality remain subjects for further evaluation.

Screenshots and software passes establish these demonstrated behaviors. They do not establish live OpenAI quality, validated triage, clinical outcomes, approved Tamil wording, verified user identities or a staffed clinical service. Those gates remain blocked in [the roadmap](../ROADMAP.md).
