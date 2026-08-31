# test_full_pipeline.py
import json
from analyze_image import analyze_drawing
from generate_story import generate_story

analysis = analyze_drawing("test_drawing.jpg")
print("辨識結果:", analysis)

story = generate_story(analysis, age=6)
print("故事:", json.dumps(story, ensure_ascii=False, indent=2))