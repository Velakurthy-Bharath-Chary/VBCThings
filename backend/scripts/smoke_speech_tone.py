from app.ai.speech_tone import analyze_tone


transcript = """
I am happy to learn computer science.
I really enjoy building software and I am excited about my future projects.
"""

result = analyze_tone(transcript)

print("\nTONE ANALYSIS:")
print(result)


# FILE PURPOSE:
# Tests transcript sentiment and tone analysis independently.