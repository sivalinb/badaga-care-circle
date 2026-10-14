"""Check local Markdown targets and safe, well-formed documentation SVGs."""
from pathlib import Path
from urllib.parse import unquote
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN = [ROOT/"README.md", ROOT/"ROADMAP.md", ROOT/"CONTRIBUTING.md", *sorted((ROOT/"docs").glob("*.md"))]
failures = []
links = 0
for path in MARKDOWN:
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"\]\(([^\s)]+)\)", text):
        if "://" in target or target.startswith("#"):
            continue
        links += 1
        resolved = (path.parent/unquote(target.split("#",1)[0])).resolve()
        if not resolved.is_relative_to(ROOT) or not resolved.exists():
            failures.append(f"{path.relative_to(ROOT)}: broken or escaping target {target}")

svgs = sorted((ROOT/"docs"/"assets").glob("*.svg"))
for path in svgs:
    try:
        tree = ET.parse(path)
        assert tree.getroot().tag.endswith("svg")
        for node in tree.iter():
            assert node.tag.rsplit("}",1)[-1] not in {"script", "foreignObject"}
            assert not any(key.lower().startswith("on") for key in node.attrib)
            assert not any(key.endswith("href") and not value.startswith("#") for key,value in node.attrib.items())
    except (ET.ParseError, AssertionError):
        failures.append(f"{path.relative_to(ROOT)}: invalid or active SVG content")
if len(svgs) != 3:
    failures.append("Expected three SVG architecture/workflow/assurance illustrations")
for name in ("demo-english.png", "demo-tamil.png", "demo-quality.png"):
    path = ROOT/"docs"/"assets"/name
    if not path.exists() or path.stat().st_size < 1000:
        failures.append(f"Missing screenshot: {name}")
if failures:
    raise SystemExit("\n".join(failures))
print(f"Verified {len(MARKDOWN)} Markdown files, {links} local links, 3 SVGs and 3 screenshots.")
