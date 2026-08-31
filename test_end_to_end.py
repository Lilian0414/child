# test_end_to_end.py
from analyze_image import analyze_drawing
from generate_story import generate_story
import requests, os
from dotenv import load_dotenv

load_dotenv()
ELEVEN_API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "hpp4J3VqNfWAUOO0d1Us"  # Bella

def text_to_speech(text, output_path):
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        headers={"xi-api-key": ELEVEN_API_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
        },
    )
    with open(output_path, "wb") as f:
        f.write(response.content)

# 完整流程
analysis = analyze_drawing("test_drawing.jpg")
story = generate_story(analysis, age=6)

print(f"故事標題：{story['title']}")
for scene in story["scenes"]:
    scene_num = scene["scene_number"]
    text_to_speech(scene["text"], f"scene_{scene_num}.mp3")
    print(f"Scene {scene_num} 語音已生成")