# analyze_image.py
import os, base64, json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(
    base_url="https://router.huggingface.co/v1",   # 指向 HF
    api_key=os.getenv("HF_TOKEN"),                  
)

def encode_image(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def analyze_drawing(image_path):
    base64_image = encode_image(image_path)

    response = client.chat.completions.create(
        model="google/gemma-4-31B-it:novita",  # 支援 vision 的模型
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一個兒童畫作分析助手。分析這張畫作，"
                    "只回傳 JSON，不要有任何其他文字或說明。"
                    "JSON 格式："
                    '{"characters": [{"name": "描述", "color": "顏色", "confidence": "high/low"}], '
                    '"scene": "場景描述", '
                    '"key_objects": ["物件1", "物件2"], '
                    '"mood_tone": "溫暖/活潑/寧靜等"}'
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "請分析這張小孩畫的畫作"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                    },
                ],
            },
        ],
        response_format={"type": "json_object"},
    )

    return json.loads(response.choices[0].message.content)

if __name__ == "__main__":
    result = analyze_drawing("test_drawing.jpg")
    print(json.dumps(result, ensure_ascii=False, indent=2))