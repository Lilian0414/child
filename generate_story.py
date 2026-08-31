# generate_story.py
import os, json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(
    base_url="https://router.huggingface.co/v1",
    api_key=os.getenv("HF_TOKEN"),
)

def generate_story(analysis_json, age=6):
    response = client.chat.completions.create(
        model="google/gemma-4-31B-it",  # 跟辨識用同一顆，或用文字模型也行
        messages=[
            {
                "role": "system",
                "content": (
                    f"你是兒童故事作家，要幫{age}歲小孩寫故事。"
                    "只回傳 JSON，格式："
                    '{"title": "故事標題", '
                    '"character_name": "主角名字", '
                    '"scenes": [{"scene_number": 1, "text": "這一幕的故事文字"}]}'
                    f"根據年齡{age}歲調整詞彙難度，"
                    f"{'4-5歲用重複句型跟狀聲詞' if age <= 5 else '6歲以上可以加入因果邏輯'}"
                ),
            },
            {
                "role": "user",
                "content": f"根據這個畫作分析生成故事：{json.dumps(analysis_json, ensure_ascii=False)}",
            },
        ],
    )

    raw_text = response.choices[0].message.content
    if not raw_text or not raw_text.strip():
        raise ValueError(f"模型回傳空內容，完整 response：{response!r}")

    text = raw_text.strip()
    # 去掉模型常見的 ```json ... ``` 包裹
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[len("json"):]
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"無法解析模型回傳的 JSON：{e}\n原始內容：{raw_text!r}") from e