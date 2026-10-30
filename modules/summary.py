"""
Generates the executive summary by synthesising all slide insights
into a single leadership narrative in one final GPT call.
This runs after all slides are processed and its output feeds both
the PDF report and the email body.
"""
from .config import MODEL


def generate_executive_summary(client, slide_results):
    """Single AI call that synthesises all slide insights into a concise exec summary.
    Skips slides with no business data. Returns a formatted string with sections:
    Overall, Key Highlights, Risks, and Priorities."""
    business_slides = [r for r in slide_results if not r["insight"].startswith("No business data")]
    if not business_slides:
        return "No business data found in this report."

    # Combine all slide insights into one block for the synthesis call
    combined = "\n\n".join(
        f"Slide {r['slide_num']}:\n{r['insight']}" for r in business_slides
    )

    prompt = f"""You are a business performance analyst writing for a leadership team.
Based ONLY on the slide insights below, write a concise executive summary.
Plain text only — no emojis, no markdown, no raw index numbers (use % comparisons like +9% vs LY).
Write like a manager reporting to leadership: precise, factual, narrative.
Use sentence case. Only capitalise proper nouns (places, brands, names) and defined abbreviations (LY, PW, CR, etc.).

Format exactly as:

Overall: [2-3 narrative sentences on WTD performance — use % vs LY/forecast/PW, name key markets, explain what drove results]

Key Highlights:
▲ [positive result, max 15 words, % context]
▲ [positive result, max 15 words, % context]
▼ [negative result, max 15 words, % context]
▼ [negative result, max 15 words, % context]

Risks:
- [risk or watch point, max 15 words]
- [risk or watch point, max 15 words]

Priorities:
- [action this week, max 15 words]
- [action this week, max 15 words]

Slide insights:
{combined}"""

    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
        max_completion_tokens=500,
    )
    return response.choices[0].message.content.strip()
