from pathlib import Path

from app.ai.vision import analyze_image


image_path = Path(__file__).with_name("test_image.png")

result = analyze_image(
    image_path,
    "Describe this image in one short sentence."
)

print("\nVISION RESULT:")
print(result)
