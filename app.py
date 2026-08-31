from flask import Flask, request, send_file, jsonify
import os, requests
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "hpp4J3VqNfWAUOO0d1Us" #Bella

@app.route("/api/tts", methods=["POST"])
def tts():
    text = request.json.get("text")
    if not text:
        return jsonify({"error": "缺少 text 參數"}), 400

    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}",
        headers={"xi-api-key": API_KEY, "Content-Type": "application/json"},
        json={
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
        },
    )

    if response.status_code != 200:
        return jsonify({"error": response.text}), response.status_code

    with open("temp_output.mp3", "wb") as f:
        f.write(response.content)

    return send_file("temp_output.mp3", mimetype="audio/mpeg")

if __name__ == "__main__":
    app.run(port=3000, debug=True)