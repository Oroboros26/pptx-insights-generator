## Writing rules (template)

Replace this file with the rules for your own reports. It is loaded into the system prompt on every run.

### Rules
- Write short, direct sentences. No introductions, no conclusions, no filler.
- Reference specific names, numbers and KPIs that appear on the slide.
- Compare to last year (LY) and forecast (fcst) when the slide shows them.
- Flag issues clearly and briefly. Add a short action note when relevant.
- Tone is professional and operational, written for a manager, not a consultant.
- Never invent data. Only state what is visible on the slide.

### Abbreviations
- LY = last year
- PY = prior year
- PW = previous week
- WoW = week over week
- YoY = year over year
- MTD / YTD / WTD = month / year / week to date
- fcst = forecast
- BUD = budget
- KPI = key performance indicator
- CR = conversion rate
- AOV = average order value
- ASP = average selling price
- UPT = units per transaction
- NPS = net promoter score
- NS = net sales
- SKU = stock keeping unit
- MD% = markdown percentage

Add your own domain terms here. The Level 2 checker in `modules/config.py` (`ABBREVIATIONS`) expects at least one known abbreviation in each insight, so keep the two lists in sync.
