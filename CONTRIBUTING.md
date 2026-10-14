# Contributing

Start with the [purpose](docs/purpose-and-pilot.md), [architecture](docs/architecture.md) and [release gates](ROADMAP.md). This repository is a fictional-data demonstration. Keep contributions and public issues limited to synthetic examples.

## Development

Use Python 3.12 and a virtual environment. Install `requirements.lock` to reproduce the tested environment, then run:

```bash
python -m pytest
python -m badaga_care eval --output evaluation_report.json
python scripts/check_docs.py
python app.py
```

`python -m badaga_care preflight` deliberately exits 2. Passing tests must not remove that clinical release block.

## Review expectations

- Explain the user problem and resulting behavior; attach relevant synthetic verification.
- For router, source, prompt or model changes, add meaningful cases and document known limits.
- For clinical/Tamil content, obtain qualified clinical and fluent-language review before claiming approval. Populate named approval metadata through an agreed publication process.
- Keep keys, raw questions, health records and exception strings out of operational traces and committed reports.
- For UI changes, check both languages, draft release, context switching and a narrow viewport.
- Update diagrams/docs when system boundaries or implemented capabilities change. Regenerate SVG assets with `python scripts/render_diagrams.py`.

Do not attach personal health records, credentials, contact lists or runtime databases to public issues or pull requests. Source cards are original summaries with linked provenance; verify content rights before adding third-party material. Future clinical deployment must satisfy the programme's human, identity, storage and referral gates, not just CI.
