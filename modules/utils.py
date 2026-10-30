"""
Shared text-processing helpers used by both pdf_report.py and email_report.py.
Centralised here to avoid duplicating parsing and formatting logic across modules.
"""
import re as _re

# Regex to strip colour emoji that bundled Inter fonts cannot render.
# The model occasionally inlines a stray glyph even after prompt constraints.
_EMOJI_RE = _re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F\U0000200D]"
)


def _clean(text):
    """Remove emoji characters that bundled fonts cannot render."""
    return _EMOJI_RE.sub("", text or "").strip()


def _abbrev_numbers(text):
    """Convert large raw integers to abbreviated form: 1,982,445 → 1.98m, 165,000 → 165k."""
    def _replace(m):
        n = int(m.group(0).replace(",", ""))
        if n >= 1_000_000:
            v = round(n / 1_000_000, 2)
            s = f"{v:.2f}".rstrip("0").rstrip(".")
            return f"{s}m"
        if n >= 10_000:
            return f"{round(n / 1_000)}k"
        return m.group(0)
    # Normalise any model-written capital M suffix (e.g. 1.24M → 1.24m)
    text = _re.sub(r"(\d)M\b", r"\1m", text)
    return _re.sub(r"\b\d{1,3}(?:,\d{3})+\b|\b\d{6,}\b", _replace, text)


def _strip_slide_header(insight, slide_num):
    """Remove the leading 'Slide N' line the model adds — the card title already shows it."""
    lines = insight.split("\n")
    filtered = []
    for line in lines:
        stripped = line.strip()
        if stripped in (f"Slide {slide_num}", f"Slide {slide_num}:"):
            continue
        filtered.append(line)
    # Drop any blank lines left at the top after the header is removed
    while filtered and not filtered[0].strip():
        filtered.pop(0)
    return "\n".join(filtered)


def _parse_exec_summary(text):
    """Parse the exec summary text into labelled sections for PDF and email rendering.
    Sections detected: overall, highlights_pos, highlights_neg, risks, priorities, watch."""
    out = {"overall": [], "highlights_pos": [], "highlights_neg": [],
           "risks": [], "priorities": [], "watch": ""}
    current = None
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        low = line.lower()
        if low.startswith("overall:"):
            current = "overall"
            rest = line[len("overall:"):].strip()
            if rest:
                out["overall"].append(rest)
        elif low.startswith("key highlights:") or low.startswith("highlights:"):
            current = "highlights"
        elif low.startswith("risks:"):
            current = "risks"
        elif low.startswith("priorities:"):
            current = "priorities"
        elif low.startswith("watch:"):
            current = "watch"
            rest = line[len("watch:"):].strip()
            if rest:
                out["watch"] = rest
        elif current == "overall":
            out["overall"].append(line)
        elif current == "highlights":
            if line.startswith(("▲", "+ ")):
                out["highlights_pos"].append(line.lstrip("▲+ ").strip())
            elif line.startswith(("▼", "- ")):
                out["highlights_neg"].append(line.lstrip("▼- ").strip())
        elif current == "risks":
            out["risks"].append(line.lstrip("-▼• ").strip())
        elif current == "priorities":
            out["priorities"].append(line.lstrip("-→• ").strip())
        elif current == "watch":
            out["watch"] = (out["watch"] + " " + line).strip()
    out["overall"] = " ".join(out["overall"])
    return out


def _parse_slide_insight(text, slide_num):
    """Parse a single slide insight into situation, observations, watch, and action fields."""
    clean = _strip_slide_header(text, slide_num)
    out = {"situation": "", "obs_pos": [], "obs_neg": [], "watch": "", "action": ""}
    in_obs = False
    for raw in clean.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("\U0001f4cd"):                              # 📍
            out["situation"] = line.lstrip("\U0001f4cd ").strip()
            in_obs = False
        elif line.startswith("\U0001f4ca") or "key observations" in line.lower():  # 📊
            in_obs = True
        elif line.startswith("⚠") or _re.match(r"^\s*watch\s*:", line, _re.IGNORECASE):
            in_obs = False
            out["watch"] = _re.sub(r"^[^\w]*watch\s*:\s*", "", line, flags=_re.IGNORECASE).strip()
            out["watch"] = out["watch"].lstrip("⚠️ ").strip()
        elif line.startswith("\U0001f3af") or _re.match(r"^\s*action\s*:", line, _re.IGNORECASE):  # 🎯
            in_obs = False
            out["action"] = _re.sub(r"^[^\w]*action\s*:\s*", "", line, flags=_re.IGNORECASE).strip()
            out["action"] = out["action"].lstrip("\U0001f3af ").strip()
        elif in_obs and line.startswith(("▲", "+ ")):
            out["obs_pos"].append(line.lstrip("▲+ ").strip())
        elif in_obs and line.startswith(("▼", "- ")):
            out["obs_neg"].append(line.lstrip("▼- ").strip())
    return out
