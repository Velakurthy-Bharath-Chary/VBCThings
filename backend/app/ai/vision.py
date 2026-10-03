import base64
from pathlib import Path

from groq import Groq

from app.config import settings


SUPPORTED_IMAGE_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

MAX_IMAGE_SIZE = 20 * 1024 * 1024


def validate_image_bytes(image_bytes: bytes, mime_type: str) -> None:
    signatures = {
        "image/jpeg": image_bytes.startswith(b"\xff\xd8\xff"),
        "image/png": image_bytes.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/webp": (
            len(image_bytes) >= 12
            and image_bytes.startswith(b"RIFF")
            and image_bytes[8:12] == b"WEBP"
        ),
    }
    if not signatures.get(mime_type, False):
        raise ValueError("Image content does not match its declared file type.")


client = Groq(api_key=settings.groq_api_key)


def analyze_image(
    file_path: str | Path,
    question: str = "Explain what is shown in this image.",
) -> str:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Image not found: {path}"
        )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_IMAGE_TYPES:
        raise ValueError(
            "Only JPG, JPEG, PNG, and WEBP images are supported."
        )

    file_size = path.stat().st_size

    if file_size > MAX_IMAGE_SIZE:
        raise ValueError(
            "Image size must not exceed 20 MB."
        )

    image_data = base64.b64encode(
        path.read_bytes()
    ).decode("utf-8")

    mime_type = SUPPORTED_IMAGE_TYPES[extension]

    image_url = (
        f"data:{mime_type};base64,{image_data}"
    )

    response = client.chat.completions.create(
        model=settings.vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": question,
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_url,
                        },
                    },
                ],
            }
        ],
        max_completion_tokens=700,
    )

    return response.choices[0].message.content or ""


# FILE PURPOSE:
# Validates image signatures and provides isolated Groq vision analysis
# for supported local image files.
