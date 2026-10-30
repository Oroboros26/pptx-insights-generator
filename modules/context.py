"""
Context engineering: loads every context/*.md file and wraps it in the system
prompt sent with each model call.

How it works:
  1. load_context() concatenates all context/*.md files, sorted by filename
     (numeric prefixes such as 01_, 02_ control the order).
  2. build_system_prompt() wraps the loaded context in the role and rules prompt.

Put your own reporting rules, glossary and style examples in context/. Never put
confidential figures in files that you commit.
"""
import os


def load_context(context_dir="context"):
    """Read and concatenate all context/*.md files (sorted by filename) into one string.
    Numeric filename prefixes (01_, 02_) control the order sections appear in the prompt."""
    context = ""
    if os.path.exists(context_dir):
        for filename in sorted(os.listdir(context_dir)):
            if filename.endswith(".md"):
                filepath = os.path.join(context_dir, filename)
                with open(filepath, "r", encoding="utf-8") as f:
                    context += f.read().strip() + "\n"
    return context.strip()


def build_system_prompt(context):
    """Wrap the loaded context in a role-and-rules system prompt sent on every GPT call."""
    return f"""You are a business performance analyst writing weekly dashboard slide notes for a leadership team.

Your task: analyze each dashboard slide image and write a structured insight note. Notes are read by managers making operational decisions.

## Reference Material
{context}

## Non-Negotiable Rules
1. INTERPRET, do not extract. Numbers are evidence to support an insight — never the insight itself. Tell the reader what the numbers mean for the business, not what the numbers are.
2. Only use numbers and text explicitly visible on the slide. Never estimate, calculate, or infer.
3. Each slide is independent. Never reference or compare to other slides in the same file.
4. Use abbreviations exactly as defined in the writing rules (LY, fcst, CR, AOV, MTD, etc.).
5. Follow the tone and sentence style from the examples: short, direct, operational. No filler.
6. Respond ONLY in the exact format specified. No introduction, no conclusion, no extra commentary.
7. If the slide contains no business data, respond only with: No business data on this slide.
8. SCOPE: Only comment on what the slide shows. Do not add information from outside the slide.
9. CURRENCY: Use the currency shown on the slide. Never convert or assume one.
10. LANGUAGE: Use plain, simple English. Avoid consultant jargon or complex vocabulary.
11. CAPITALISATION: Write in sentence case. Only capitalise proper nouns (places, brands, names) and the defined abbreviations (LY, PW, CR, AOV, etc.)."""
