import os
import base64
import traceback
from io import BytesIO
from typing import Optional, Tuple

from PIL import Image
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response, PlainTextResponse
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables (e.g., GEMINI_API_KEY)
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY is not set")

# Configure Gemini
TRYON_MODEL = os.getenv("TRYON_MODEL", "gemini-1.5-flash")
genai.configure(api_key=api_key)
model = genai.GenerativeModel(TRYON_MODEL)

MAX_SIDE = int(os.getenv("TRYON_MAX_SIDE", "1024"))

def downscale(img: Image.Image, max_side: int = MAX_SIDE) -> Image.Image:
    w, h = img.size
    scale = min(1.0, float(max_side) / max(w, h))
    if scale < 1.0:
        new_size = (int(w * scale), int(h * scale))
        return img.resize(new_size, Image.LANCZOS)
    return img


def file_to_image_part(file_bytes: bytes, mime: str = "image/png"):
    """Convert raw bytes to the inline_data format expected by Gemini vision models."""
    img = Image.open(BytesIO(file_bytes)).convert("RGB")
    img = downscale(img, MAX_SIDE)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return {"mime_type": mime, "data": buf.getvalue()}

PROMPT = (
    "ROLE: You are a professional virtual try-on compositor.\n"
    "INPUTS: Image A (person), Image B (product). OUTPUT: one edited image only.\n\n"
    "GOAL: Place the product from Image B onto the person in Image A so it looks naturally worn/held.\n\n"
    "HARD CONSTRAINTS (must all be true):\n"
    "- Edit the minimal region necessary; keep the rest of Image A pixel-accurate.\n"
    "- Do NOT add or duplicate body parts. Keep exactly two arms and two hands with the same pose and finger count as in Image A.\n"
    "- Do NOT change the person’s pose, proportions, face, skin tone, hair, clothing (except where the product must attach), or background.\n"
    "- Render exactly ONE instance of the product. No duplicates, reflections, or floating copies.\n"
    "- If placement would require inventing new limbs/fingers, instead keep the original limb and partially occlude the product behind it.\n\n"
    "PLACEMENT POLICY (choose the most plausible anchor automatically):\n"
    "- Head/face: glasses, hats.\n"
    "- Torso/upper body: shirts, jackets, necklaces, ties, scarves.\n"
    "- Wrist/forearm: watches, bracelets, bangles.\n"
    "- Hand/fingers: rings, gloves.\n"
    "- Waist/hips: belts, bags with straps.\n"
    "- Feet: shoes/sneakers.\n"
    "- Shoulder/back: backpacks, shoulder bags.\n"
    "Match the person’s perspective and pose; allow natural occlusions by hair, hands, or clothing.\n\n"
    "RENDERING REQUIREMENTS:\n"
    "- Match lighting, color balance, shadows, and scale; keep edges clean and anti-aliased.\n"
    "- Avoid artifacts: no extra limbs/hands/fingers, no warped anatomy, no duplicated sleeves, no ghosting, no text glitches.\n\n"
    "QUALITY SELF-CHECK before finalizing (must pass all):\n"
    "1) Exactly two hands and two arms, identical pose to Image A.\n"
    "2) Face and background unchanged.\n"
    "3) One product instance only, correctly attached and scaled.\n"
    "4) Edges/shadows look photographic.\n"
    "If any check fails, correct it and output the fixed image.\n\n"
    "Return only the final edited image."
)

GENERATION_CONFIG = {"temperature": 0.4}

app = FastAPI(title="Try-On Service", version="1.0.0")

@app.get("/_healthz", response_class=PlainTextResponse)
def healthz():
    return "ok"

@app.post("/tryon")
async def tryon(human_image: UploadFile = File(...), product_image: UploadFile = File(...)):
    try:
        human_bytes = await human_image.read()
        product_bytes = await product_image.read()
        if not human_bytes or not product_bytes:
            raise HTTPException(status_code=400, detail="Both images are required")

        person_part = file_to_image_part(human_bytes)
        product_part = file_to_image_part(product_bytes)

        try:
            resp = model.generate_content(
                [PROMPT, person_part, product_part],
                generation_config=GENERATION_CONFIG,
                request_options={"timeout": 180},
            )
        except Exception as ge:
            # Log full traceback server-side
            print("[tryon] generate_content failed:\n" + traceback.format_exc())
            # Surface a useful error message
            raise HTTPException(status_code=502, detail=f"Generation call failed: {str(ge)}")

        # Extract the first inline image from response
        img_bytes: Optional[bytes] = None
        if getattr(resp, "candidates", None):
            for cand in resp.candidates:
                content = getattr(cand, "content", None)
                if not content:
                    continue
                for part in getattr(content, "parts", []):
                    inline = getattr(part, "inline_data", None)
                    if inline and getattr(inline, "data", None) is not None:
                        data = inline.data
                        if isinstance(data, str):
                            data = base64.b64decode(data)
                        img_bytes = data
                        break
                if img_bytes:
                    break
        if not img_bytes:
            # Try to include additional info if available
            details = getattr(resp, "text", None) or str(getattr(resp, "prompt_feedback", "No image generated"))
            raise HTTPException(status_code=502, detail=f"No image generated: {details}")

        return Response(content=img_bytes, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        print("[tryon] Unexpected error:\n" + traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# If running directly: uvicorn try_on:app --host 0.0.0.0 --port 8080
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("try_on:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")))