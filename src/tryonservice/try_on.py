import os, base64
from io import BytesIO
from PIL import Image
import google.generativeai as genai

# 0) Configure
genai.configure(api_key="AIzaSyAUix5Lc7A8ytsnq4TLe8LqS0_CcUWJ56g")


def load_image_part(path, mime="image/png"):
    img = Image.open(path).convert("RGB")
    buf = BytesIO()
    # use PNG so alpha/masks aren't a problem
    img.save(buf, format="PNG")
    return {"mime_type": mime, "data": buf.getvalue()}

model_image_path = "/Users/maryshermila/Desktop/STUDY MATERIALS/google-hackathon/online-boutique/src/tryonservice/templates/human.png"
product_image_path = "/Users/maryshermila/Desktop/STUDY MATERIALS/google-hackathon/online-boutique/src/tryonservice/templates/watch.png"
output_image_path = "/Users/maryshermila/Desktop/STUDY MATERIALS/google-hackathon/online-boutique/src/tryonservice/templates/virtual_try_on_result.png"

model_image  = load_image_part(model_image_path)
product_image = load_image_part(product_image_path)

model = genai.GenerativeModel("gemini-2.5-flash-image-preview")

# --- Prompt ---
prompt = (
    "Your task is to place the product from the second image onto the person in the first image. "
    "You MUST follow these rules carefully:\n"
    "1.  **Edit the existing person; DO NOT generate new body parts.** Modify the person's left wrist to realistically wear the watch.\n"
    "2.  **Preserve the original pose.** Do not change the position of the arms, hands, or body.\n"
    "3.  **Maintain identity and background.** The person's face, skin tone, clothing, and the background must remain unchanged.\n"
    "4.  **No artifacts.** It is critical to avoid generating extra limbs, hands, or fingers. The result must be photorealistic and anatomically correct.\n"
    "5.  **Blend seamlessly.** Ensure lighting, shadows, and the fit of the watch on the wrist are natural."
)

# Ask explicitly for an image back:
generation_config = {
    "temperature": 0.4,
    "response_mime_type": "image/png",   # <- crucial for 0.8.x to return an image blob
}

resp = model.generate_content(
    [prompt, model_image, product_image],
    generation_config=generation_config,
    request_options={"timeout": 120},
)

# 5) Robust extraction of the returned image
def save_first_image_from_response(response, path):
    """
    Handles common shapes in google-generativeai 0.8.x:
      - candidates[].content.parts[].inline_data (bytes or base64 str)
      - candidates[].content.parts[].file_data (needs download via media API; not common for this call)
      - text fallback
    """

    if not getattr(response, "candidates", None):
        # Sometimes the SDK returns text-only with prompt feedback
        txt = getattr(response, "text", "") or str(getattr(response, "prompt_feedback", ""))
        raise RuntimeError(f"No image candidates. Text response: {txt}")

    for cand in response.candidates:
        content = getattr(cand, "content", None)
        if not content:
            continue
        for part in getattr(content, "parts", []):
            # 1) inline_data (preferred)
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None) is not None:
                data = inline.data
                # data may be bytes or a base64-encoded string depending on version
                if isinstance(data, str):
                    data = base64.b64decode(data)
                img = Image.open(BytesIO(data))
                img.save(path)
                return True

            # 2) Some API versions return .text – not an image
            if getattr(part, "text", None):
                # Keep going; maybe another part has the image
                continue

    # If we got here, no inline image was present
    txt = getattr(response, "text", "") or "No image parts returned."
    raise RuntimeError(f"Could not find an image in the response. Details: {txt}")

# 6) Save
saved = save_first_image_from_response(resp, output_image_path)
print(f"SUCCESS! Saved to: {output_image_path}" if saved else "No image saved.")