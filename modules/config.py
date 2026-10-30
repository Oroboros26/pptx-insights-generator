# All shared constants. Import from here — never hardcode values in other modules.

# Azure OpenAI deployment used for every API call (slide analysis, judge, exec summary).
# Set AZURE_OPENAI_DEPLOYMENT in .env to match your own deployment name.
import os
MODEL = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

# Fraction of L2-passing slides also sent to the L3 AI judge for spot-checking
SAMPLE_RATE = 0.20

# Output format contract — emoji markers (📍 📊 ▲ ▼ ⚠️ 🎯) are parsed by
# utils.py to build the PDF and email. Changing this format without updating
# the parsers in utils.py silently breaks PDF and email output.
SLIDE_PROMPT = """You are a senior retail analyst writing slide notes for a business leadership team.

RULES:
- INTERPRET, do not copy numbers. Tell the reader what the data means for the business.
- BAD: "Online share 72%, -0.1pts vs PW" — just copying.
- GOOD: "Online losing share to stores for a second week; basket mix shifting."
- Index ratios on slides (1.09 = +9%, 0.96 = -4%). Always write as % — never raw ratios.
- Write abbreviated numbers: 1.98m not 1,982,445. Keep % comparisons brief.

Respond ONLY in this exact format (no "Slide N" header, no section labels after emojis):

📍 [1 sentence — overall story this week, % as supporting evidence, not the main point]

📊 Key observations:
▲ [what is working and why, max 12 words]
▼ [what is underperforming and what it signals, max 12 words]
▲ or ▼ [third key observation, max 12 words]

⚠️ Watch: [risk or trend to monitor next week, max 12 words]
🎯 Action: [concrete action for the team or manager, max 12 words]

If no business data, respond with: No business data on this slide."""

# Level 2 validator checks that the model used these abbreviations (style guard)
ABBREVIATIONS = {
    "LY", "PY", "PW", "WoW", "YoY", "MTD", "YTD", "WTD", "fcst", "BUD",
    "KPI", "CR", "AOV", "ASP", "UPT", "NPS", "NS", "SKU", "MD%"
}

# Level 2 validator flags these phrases as likely hallucination
HALLUCINATION_SIGNALS = [
    "approximately", "likely", "estimated", "i think",
    "probably", "around", "roughly", "seems", "appears to"
]
