# test_tts.py
import os, requests
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "hpp4J3VqNfWAUOO0d1Us" #Bella
url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}"

response = requests.post(
    url,
    headers={
        "xi-api-key": API_KEY,
        "Content-Type": "application/json",
    },
    json={
        "text": "波波發現了一朵藍色的玫瑰，牠決定送給生病的朋友。",
        "model_id": "eleven_multilingual_v2",  # 中文一定要用這個
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
        },
    },
)

if response.status_code == 200:
    with open("output.mp3", "wb") as f:
        f.write(response.content)
    print("成功！存成 output.mp3")
else:
    print("失敗:", response.status_code, response.text)