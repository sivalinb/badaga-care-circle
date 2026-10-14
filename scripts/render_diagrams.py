"""Generate editable documentation SVGs with the Python standard library."""
from html import escape
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
COLORS = {
    "ink": "#183747", "muted": "#526b77", "line": "#6b8591",
    "green": "#14796b", "green_bg": "#e9f5ef", "blue": "#24647d", "blue_bg": "#edf4f9",
    "purple": "#7652a5", "purple_bg": "#f3eefb", "amber": "#976623", "amber_bg": "#fff5e5",
    "red": "#a34c43", "red_bg": "#fcefeb",
}


class Diagram:
    def __init__(self, height, title, subtitle, description):
        self.height = height
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="1320" height="{height}" viewBox="0 0 1320 {height}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title><desc id="desc">{escape(description)}</desc>',
            '<defs><marker id="arrow" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto-start-reverse"><path d="M0,0 L9,4.5 L0,9" fill="#6b8591"/></marker></defs>',
            '<rect width="1320" height="100%" fill="#fafbf7"/>',
            '<rect width="1320" height="126" fill="#183747"/>',
        ]
        self.text(48, 48, "BADAGA CARE CIRCLE  /  FICTIONAL-DATA DEMO", 14, "#afe0cc", 700)
        self.text(48, 88, title, 30, "#ffffff", 700)
        self.text(48, 152, subtitle, 18, COLORS["muted"])

    def text(self, x, y, value, size=18, color=None, weight=400):
        self.parts.append(f'<text x="{x}" y="{y}" font-family="Arial, Helvetica, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color or COLORS["ink"]}">{escape(value)}</text>')

    def card(self, x, y, w, h, label, title, lines, kind="green", dashed=False):
        dash = ' stroke-dasharray="8 6"' if dashed else ""
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{COLORS[kind+"_bg"]}" stroke="{COLORS[kind]}" stroke-width="1.6"{dash}/>')
        self.text(x+22, y+30, label.upper(), 12, COLORS[kind], 700)
        title_lines = textwrap.wrap(title, width=max(20, int((w-44)/11)))
        for i, part in enumerate(title_lines):
            self.text(x+22, y+60+i*27, part, 22, COLORS["ink"], 700)
        cy = y+91+27*(len(title_lines)-1)
        for line in lines:
            for part in textwrap.wrap(line, width=max(20, int((w-44)/9))):
                self.text(x+22, cy, part, 17, COLORS["muted"])
                cy += 24
        last_baseline = cy-24 if lines else y+60+27*(len(title_lines)-1)
        if last_baseline > y+h-12:
            raise ValueError(f"Text exceeds card height: {title}")

    def arrow(self, points, label=None, lx=None, ly=None, dashed=False):
        coords = " ".join(f"{x},{y}" for x,y in points)
        dash = ' stroke-dasharray="7 6"' if dashed else ""
        self.parts.append(f'<polyline points="{coords}" fill="none" stroke="{COLORS["line"]}" stroke-width="2" marker-end="url(#arrow)"{dash}/>')
        if label:
            self.text(lx, ly, label, 14, COLORS["muted"])

    def footer(self, value):
        self.text(48, self.height-25, value, 14, COLORS["muted"])

    def save(self, name):
        ASSETS.mkdir(parents=True, exist_ok=True)
        (ASSETS/name).write_text("\n".join([*self.parts, "</svg>"]), encoding="utf-8")


def architecture():
    d = Diagram(1100, "Architecture: a small system with visible boundaries",
                "One local Python process; arrows show the main education path and review handover.",
                "Gradio calls scoped CareService and a fixed safety gate. Education uses bilingual retrieval, optional consented OpenAI drafts, and human review before release. Fictional workflows and minimized traces persist in SQLite. Clinical pilot gates remain unmet.")
    d.card(48, 190, 360, 160, "Interface / ui.py + i18n.py", "English / Tamil browser", ["Gradio Blocks and session state", "Residents, caretakers and reviewers"], "blue")
    d.card(480, 190, 360, 160, "Application / service.py", "Scoped CareService", ["Household + role + consent", "Workflow ordering and fallbacks"])
    d.card(912, 190, 360, 160, "Rules / safety.py", "Fixed safety gate", ["Warnings and medicine boundaries", "Fixed routes bypass optional AI"], "amber")
    d.arrow([(408,270),(474,270)])
    d.arrow([(840,270),(906,270)])
    d.card(48, 420, 360, 164, "Evidence / knowledge.json", "12 bilingual source cards", ["URLs, versions, expiry and tags", "Clinical / Tamil approval pending"], "blue")
    d.card(480, 420, 360, 164, "Retrieval / retrieval.py", "Hybrid local retrieval", ["BM25 + character TF-IDF", "Optional dense score fusion"])
    d.card(912, 420, 360, 164, "Optional cloud / providers.py", "OpenAI API boundary", ["Embeddings + structured draft", "Configuration and cloud consent"], "purple", True)
    d.arrow([(1092,350),(1092,382),(660,382),(660,414)], "general education", 718, 374)
    d.arrow([(408,502),(474,502)])
    d.arrow([(840,502),(906,502)], dashed=True)
    d.parts.append('<rect x="48" y="604" width="360" height="46" rx="12" fill="#edf4f9" stroke="#24647d" stroke-width="1.4"/>')
    d.text(66,633,"Default local mode: linked excerpts",18,COLORS["blue"],700)
    d.arrow([(540,584),(540,628),(414,628)])
    d.card(48, 668, 360, 164, "Persistence / storage.py", "Local fictional SQLite", ["Check-ins, tasks and family backup", "Review queue, traces and audits"], "blue")
    d.card(480, 668, 360, 164, "Human in the loop", "Inspect, note and decide", ["Education: approve / reject", "Check-in: follow-up / close"])
    d.card(912, 668, 360, 164, "Release / service.py", "Scoped approved draft", ["Same language and household", "Recheck source version and expiry"])
    d.arrow([(660,584),(660,662)], "template", 566, 625)
    d.arrow([(1092,584),(1092,620),(730,620),(730,662)], "validated AI draft", 854, 611, True)
    d.arrow([(474,750),(414,750)])
    d.arrow([(840,750),(906,750)])
    d.card(48, 874, 1224, 82, "Implemented operational evidence", "Redacted guide traces + local latency / token / fallback metrics + action audits", [], "green")
    d.card(48, 980, 1224, 78, "Future clinical pilot gate", "Named clinical owners + approved bilingual content + verified identity + protected storage", [], "red")
    d.footer("Demo role selectors are not authentication. Current software does not place calls, send messages or book care.")
    d.save("architecture.svg")


def workflows():
    d = Diagram(1210, "Flows: turn concern into a reviewed answer and a handover",
                "Every illustration uses fictional households. Fixed warning guidance does not wait for a reviewer.",
                "General education goes through a safety gate and source retrieval, optional drafting, human approval and scoped release. BP check-ins require confirmation and consent. Tasks move from requested to accepted to completed. Backup plans require two adults and rehearsal.")
    xs = [48, 360, 672, 984]
    cards = [
        ("01 / member", "Ask in English / Tamil", ["Select demo context", "General care question"], "blue"),
        ("02 / application", "Gate and retrieve", ["Fixed routes first", "Find linked evidence"], "amber"),
        ("03 / draft mode", "Withhold the draft", ["Local template or AI", "Show source excerpts"], "purple"),
        ("04 / reviewer", "Review and release", ["Inspect + required notes", "Approve + freshness check"], "green"),
    ]
    for x,(label,title,lines,kind) in zip(xs,cards):
        d.card(x,190,288,190,label,title,lines,kind)
    for x in xs[:-1]:
        d.arrow([(x+288,282),(x+306,282)])
    d.card(48, 418, 1224, 90, "Current warning route", "Fixed emergency guidance appears immediately; optional AI and review are bypassed.", [], "red")
    d.text(48, 555, "THREE PRACTICAL WORKFLOWS", 15, COLORS["green"], 700)
    rows = [
        (582,"BP check-in", ["Confirm values + consent", "Save check-in + review atomically", "Human follow-up / close"], "blue"),
        (750,"Shared care task", ["Request with sharing consent", "Record helper acceptance", "Record task completion"], "green"),
        (918,"Family backup", ["Choose two distinct adults", "Share routines and locations", "Practise and record rehearsal"], "amber"),
    ]
    for y,label,steps,kind in rows:
        for i,(x,step) in enumerate(zip([48,480,912],steps)):
            d.card(x,y,360,130,f"{label} / {i+1:02}",step,[],kind)
        d.arrow([(408,y+75),(474,y+75)])
        d.arrow([(840,y+75),(906,y+75)])
    d.card(48, 1090, 1224, 76, "Language and scope", "Saved notes keep their original language; unsaved inputs clear when demo context changes.", [], "blue")
    d.footer("No reminder, booking or remote helper acceptance is sent by this demo. Staffed pathways belong to the pilot roadmap.")
    d.save("workflows.svg")


def assurance():
    d = Diagram(1210, "Assurance: software evidence, operational signals, human gates",
                "A passing regression suite does not establish clinical safety, fluent Tamil or delivered care.",
                "Three pillars describe software regression tests, minimized local request traces and metrics, and human clinical/language review gates. The build has 53 tests, 46 synthetic cases and 11 earlier browser checks. Live OpenAI and clinical field validation are absent.")
    for x,label,title,lines,kind in [
        (48,"Repeatable software checks", "Evaluate behavior", ["46 cases: 30 English / 16 Tamil", "30 cases marked critical", "Routes and expected source IDs"],"blue"),
        (480,"Local operational evidence", "Observe the pipeline", ["Random trace ID and UTC time", "Route, provider, status, sources", "Safety / retrieval / draft timing"],"green"),
        (912,"Accountable human ownership", "Approve the programme", ["Clinician and Tamil reviewer", "Resident usability sessions", "Staffed referral agreement"],"amber"),
    ]:
        d.card(x,190,360,210,label,title,lines,kind)
    d.card(48, 436, 360, 188, "Workflow / provider contracts", "53 Python tests", ["Scope, consent and state changes", "Expiry, API failures and redaction", "SDK transport tests; no live API"], "blue")
    d.card(480, 436, 360, 188, "Current dashboard window", "Latest 1,000 requests", ["p95 latency approximation", "Input / output token totals", "Provider and status counts"], "green")
    d.card(912, 436, 360, 188, "Current approval status", "Clinical release blocked", ["Medical / Tamil drafts unapproved", "Identity and storage need hardening", "No clinical field validation"], "red")
    d.card(48, 660, 360, 188, "Build-time UI verification", "11 browser checks", ["English / Tamil and human review", "Care tasks, check-ins and backup", "390px layout; zero JS errors"], "blue")
    d.card(480, 660, 360, 188, "Trace field minimization", "Exclude raw private input", ["No questions or BP values", "No household IDs or keys", "No provider exception strings"], "green")
    d.card(912, 660, 360, 188, "Supervised pilot outcomes", "Check completed care", ["Screening and referral completion", "Practical help actually delivered", "Trust, accessibility and workload"], "amber")
    d.card(48, 892, 1224, 90, "Repository automation", "CI repeats tests + offline eval + documentation checks + expected blocked preflight.", [], "blue")
    d.card(48, 1018, 1224, 112, "Known limits", "No live-model quality score or external monitoring service is implemented.", ["Synthetic pass counts and token totals do not measure clinical efficacy or prevent sudden death."], "red")
    d.footer("See docs/evaluations.md and docs/observability.md for exact checks, trace fields, limitations and roadmap work.")
    d.save("assurance.svg")


if __name__ == "__main__":
    architecture()
    workflows()
    assurance()
    print("Generated three documentation SVG illustrations.")
