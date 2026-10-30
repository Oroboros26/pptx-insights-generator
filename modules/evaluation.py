"""
Two-gate quality system for AI-generated slide insights.

Level 2 — rule-based (fast, free, runs on every slide):
  Checks required sections exist, bullets are within word limits,
  no hallucination hedge words, and at least one known abbreviation is used.

Level 3 — AI-as-judge (costs an extra API call):
  A second GPT call scores accuracy / format / tone 1–5.
  Only fires on L2 failures + a random SAMPLE_RATE % of L2 passes.

Neither level blocks output — they flag issues in the quality report.
"""
import json    # parse the Level 3 judge's JSON response

from .config import MODEL, ABBREVIATIONS, HALLUCINATION_SIGNALS


def validate_insight(insight):
    """Level 2: fast rule-based checks. Returns a list of flag strings (empty list = pass)."""
    flags = []

    if insight.strip().startswith("No business data"):
        return flags  # no-data slides are always valid — nothing to check

    # Required structural sections (from SLIDE_PROMPT format)
    for section in ["Watch:", "Action:"]:
        if section not in insight:
            flags.append(f"missing section: {section}")

    # Bullet word-count limit (SLIDE_PROMPT specifies max 12 words per bullet)
    for line in insight.split("\n"):
        line = line.strip()
        if line.startswith(("▲ ", "▼ ", "- ")):
            words = len(line[2:].strip().split())
            if words > 12:
                flags.append(f"bullet too long ({words} words): '{line[:50]}'")

    # Hedge words signal the model invented data it couldn't see on the slide
    lower = insight.lower()
    for signal in HALLUCINATION_SIGNALS:
        if signal in lower:
            flags.append(f"hallucination signal: '{signal}'")

    # At least one known abbreviation must appear (style guide compliance)
    if not any(abbr in insight for abbr in ABBREVIATIONS):
        flags.append("no known abbreviations used — style guide may have been ignored")

    return flags


def judge_insight(client, b64_image, insight, slide_num):
    """Level 3: AI-as-judge. A second GPT call scores accuracy/format/tone 1–5.
    Returns a dict: {accuracy, format, tone, flags}."""
    judge_prompt = f"""You are a quality reviewer for business performance reporting.

Below is an AI-generated insight note for Slide {slide_num}. Review it against the slide image.

Score each dimension 1–5:
- accuracy: only reports numbers/text explicitly visible on the slide (5 = perfect, 1 = invented data)
- format: follows the required structure exactly (5 = perfect, 1 = wrong structure)
- tone: concise, operational, uses business abbreviations correctly (5 = perfect, 1 = verbose/wrong tone)

Respond ONLY as valid JSON with no extra text:
{{"accuracy": <int>, "format": <int>, "tone": <int>, "flags": [<string>, ...]}}

Insight to review:
{insight}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}},
                    {"type": "text", "text": judge_prompt}
                ]
            }
        ],
        temperature=0.0,           # zero temperature = deterministic scoring
        max_completion_tokens=200,
    )
    try:
        return json.loads(response.choices[0].message.content.strip())
    except (json.JSONDecodeError, ValueError):
        return {"accuracy": 0, "format": 0, "tone": 0, "flags": ["judge returned invalid JSON"]}


def print_quality_report(slide_results, sample_rate):
    """Print a summary table of L2/L3 results after all slides are processed."""
    total      = len(slide_results)
    l2_passed  = sum(1 for r in slide_results if r["l2_passed"])
    l3_results = [r for r in slide_results if r.get("l3_result")]

    print("\n" + "═" * 52)
    print("  QUALITY REPORT")
    print("═" * 52)
    print(f"  Slides processed : {total}")
    print(f"  Level 2 passed   : {l2_passed}/{total}")

    if l3_results:
        avg_acc  = sum(r["l3_result"]["accuracy"] for r in l3_results) / len(l3_results)
        avg_fmt  = sum(r["l3_result"]["format"]   for r in l3_results) / len(l3_results)
        avg_tone = sum(r["l3_result"]["tone"]      for r in l3_results) / len(l3_results)
        print(f"  Level 3 judged   : {len(l3_results)}/{total} slides (random {int(sample_rate * 100)}% + L2 failures)")
        print(f"    Accuracy : {avg_acc:.1f}/5")
        print(f"    Format   : {avg_fmt:.1f}/5")
        print(f"    Tone     : {avg_tone:.1f}/5")

    # Slides flagged = L2 failure OR any L3 dimension scored below 3
    flagged = [
        r for r in slide_results
        if not r["l2_passed"]
        or (r.get("l3_result") and min(
            r["l3_result"]["accuracy"],
            r["l3_result"]["format"],
            r["l3_result"]["tone"]
        ) < 3)
    ]

    if flagged:
        print("\n  Slides needing review:")
        for r in flagged:
            print(f"    Slide {r['slide_num']}:")
            for flag in r["l2_flags"]:
                print(f"      ⚠️  {flag}")
            if r.get("l3_result") and r["l3_result"].get("flags"):
                for flag in r["l3_result"]["flags"]:
                    print(f"      🧑‍⚖️  {flag}")
    else:
        print("\n  All slides passed. No issues found.")

    print("═" * 52)
