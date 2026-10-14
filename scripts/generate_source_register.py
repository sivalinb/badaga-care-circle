"""Render the public source metadata already present in the knowledge file."""
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
docs = json.loads((ROOT/"data"/"knowledge.json").read_text(encoding="utf-8"))
lines = [
    "# Public knowledge-source register", "",
    "[Home](../README.md) · [AI and RAG](ai-and-rag.md) · [Evaluations](evaluations.md)", "",
    "The twelve cards are original brief English/Tamil summaries with linked provenance, not copied medical publications. All are `demo_draft`, with clinical and language approval pending. Checked dates document build-time source review; they are not clinical sign-off. The app does not crawl or automatically refresh these sources.", "",
    "| Card ID | Topic / linked primary source | Version | Checked | Expires | Review |",
    "|---|---|---|---|---|---|",
]
for d in docs:
    source = f'[{d["source_name"]}]({d["source_url"]})' if d["source_url"] else d["source_name"]
    lines.append(f'| `{d["id"]}` | {d["title"]["en"]} — {source} | {d["version"]} | {d["source_checked"]} | {d["expires_on"]} | {d["review_status"]} |')
lines += ["", "The Nilgiris ambulance reference is a source link, not a calling integration. Community practice cards are labelled as proposed programme practices where applicable. Confirm local pathways, source permissions, medical wording and Tamil meaning before a pilot. Every card needs named clinical/language reviewers and a review-by date in the agreed publication process.", "", "The complete bilingual text, tags, approval fields and reuse notes live in [`data/knowledge.json`](../data/knowledge.json). Expired cards are excluded; approved draft release rechecks source versions and expiry. See [architecture](architecture.md) and [the roadmap](../ROADMAP.md).", ""]
(ROOT/"docs"/"sources.md").write_text("\n".join(lines),encoding="utf-8")
print("Generated public knowledge-source register.")
