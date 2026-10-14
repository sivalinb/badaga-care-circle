# Technologies used and why

[Home](../README.md) · [Architecture](architecture.md) · [AI and RAG](ai-and-rag.md)

These choices describe the implemented local demo. The top-level versions below come from [`requirements.txt`](../requirements.txt); [`requirements.lock`](../requirements.lock) records the tested transitive environment. They are reproducibility pins, not a claim that each is the newest or best version for a clinical deployment.

| Technology | Version / status | Role | Reason and tradeoff |
|---|---|---|---|
| Python | 3.12 used; project requires ≥3.12 | Application, workflows and developer commands | One readable implementation for service, retrieval, persistence and evaluation |
| Gradio Blocks | 6.30.0 | Interactive demo and language/role/household context | Quick demonstration with forms and event handlers; the role selector is not authentication |
| Explicit English/Tamil dictionaries | Implemented in `i18n.py` | Labels, fixed guidance, options and roadmap | Predictable reviewed-copy workflow; translations are currently unreviewed drafts |
| BM25 | Local implementation | Topic-token ranking | No model download or API required; exact wording and small lexicon limit recall |
| scikit-learn | 1.9.1 | Character TF-IDF retrieval | Character n-grams help with Tamil roots/suffixes; similarity does not imply medical support |
| NumPy | 2.5.4 | Retrieval score arrays, normalization and cosine similarity | Adequate for twelve cards; no separate vector service needed |
| Pydantic | 2.14.1 | Structured draft schema | Bounds output shape and lengths; schema validity is not factual validity |
| OpenAI Python SDK | 2.54.0, optional at runtime | Responses API parsing and embeddings | Explicit consent/configuration, timeout and fallback; live output quality is untested |
| `text-embedding-3-small` | Optional configurable default | Dense corpus/question representations | Can add semantic matching; cloud use sends the question to the provider |
| SQLite / `sqlite3` | Python standard library | Fictional check-ins, tasks, backup, reviews, traces and audits | Local transactions with no server setup; not an encrypted clinical-data service |
| python-dotenv | 1.2.4 | Optional `.env` configuration | Keeps keys out of source/UI; `.env` is excluded from publication |
| pytest | 9.1.1 | Unit and integration regression tests | Temporary stores and provider doubles keep checks repeatable/offline |
| OpenAI SDK + HTTPX MockTransport | Test-only use | Real SDK request/response contract | Exercises serialization without spending tokens; cannot assess live model quality |
| Playwright / Chromium | Build verification tooling | Eleven browser workflow checks and mobile layout inspection | Build report and fictional screenshots are included; browser automation is not in current CI |
| JSON reports | Implemented | Evaluation and build evidence | Machine-readable results with explicit clinical/live-API limits |
| SVG + Mermaid | Implemented documentation | Architecture, flow and assurance illustrations | Editable vector assets and GitHub-rendered engineering diagrams |
| GitHub Actions | Repository workflow | Python tests, offline eval, documentation and preflight checks | Read-only source permission, pinned official actions and no API secret |

## Deliberately small runtime

The browser, one local Python service, JSON knowledge files and SQLite are sufficient for this demonstration. There is no separate orchestration framework, vector database, autonomous agent, hosted monitoring collector or messaging service in the runtime. The optional LLM assists only with a withheld education draft. It does not choose clinical actions, send messages or schedule care.

## Alternatives and when they become useful

| Need that emerges in a real pilot | Candidate direction | Prerequisite |
|---|---|---|
| Verified household and staff identities | An identity provider and server-enforced membership | Agreed enrolment and access model |
| Protected clinical storage and concurrency | Managed relational store, encryption, backups and migrations | Clinical/data governance and restore drills |
| More approved knowledge and corpus updates | Approved publication pipeline; evaluate search/vector infrastructure as volume grows | Source rights, clinical/language sign-off and held-out retrieval evals |
| Staffed follow-up and reminders | Background jobs and an agreed private messaging/clinic integration | Opt-in, due dates, receiving team and failure escalation |
| Fleet monitoring and dashboards | OpenTelemetry-compatible spans and a selected monitoring backend | Field minimization, retention policy and access controls |
| Badaga audio and accessibility | Reviewed recorded audio and user-tested interactions | Fluent community reviewers and consent for recordings |

These are roadmap options, not installed features. Select them after local programme requirements are established; changing tools does not satisfy clinical release gates by itself.

## Official technical references

- [Gradio Blocks](https://www.gradio.app/docs/gradio/blocks)
- [OpenAI Responses API](https://developers.openai.com/api/reference/resources/responses)
- [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI embeddings](https://developers.openai.com/api/docs/guides/embeddings)
- [scikit-learn text feature extraction](https://scikit-learn.org/stable/modules/feature_extraction.html#text-feature-extraction)
- [Python SQLite](https://docs.python.org/3/library/sqlite3.html)
- [pytest](https://docs.pytest.org/en/stable/)
- [Official checkout](https://github.com/actions/checkout), [Python setup](https://github.com/actions/setup-python) and [artifact upload](https://github.com/actions/upload-artifact) actions
