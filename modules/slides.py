"""
Slide image extraction, GPT-vision analysis, and writing results back into PPTX.
Each slide is processed independently — no cross-slide context is ever passed.
"""
import base64    # encode slide image to base64 before sending to the API
import io        # in-memory byte streams for image conversion (no temp files)

from PIL import Image    # open the embedded slide picture and convert to PNG

from .config import MODEL, SLIDE_PROMPT


def extract_slide_image(slide):
    """Extract the embedded picture from a slide and return it as a base64 PNG string.
    shape_type == 13 is the python-pptx constant for an embedded picture object.
    Returns None if the slide has no embedded image (e.g. title or text-only slides)."""
    for shape in slide.shapes:
        if shape.shape_type == 13:
            image_bytes = shape.image.blob
            img = Image.open(io.BytesIO(image_bytes))
            output = io.BytesIO()
            img.save(output, format="PNG")
            output.seek(0)
            # base64 converts binary image bytes into a text string safe to embed in JSON
            return base64.b64encode(output.read()).decode("utf-8")
    return None


def analyze_slide(client, b64_image, slide_num, system_prompt):
    """Send a slide image to the GPT vision model and return the structured insight text.
    The image is base64-encoded and sent inline as a data URI alongside the text prompt."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    # Inline image sent as a data URI — no external URL or file upload needed
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64_image}"}},
                    {"type": "text", "text": SLIDE_PROMPT}
                ]
            }
        ],
        temperature=0.2,          # low temperature = more consistent, less creative output
        max_completion_tokens=800,
    )
    usage = response.usage
    print(f"    tokens → input: {usage.prompt_tokens} | output: {usage.completion_tokens}")
    return response.choices[0].message.content.strip()


def write_notes(slide, insight):
    """Write the AI insight text into the slide's speaker notes field."""
    notes_slide = slide.notes_slide
    tf = notes_slide.notes_text_frame
    tf.clear()
    tf.text = insight
