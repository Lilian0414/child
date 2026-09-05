"""Opt-in OpenAI-compatible vision HTTP adapter using only the standard library."""

import base64
import json
from urllib.request import Request, urlopen

from child_agent_api.observer import ImageInput, ProviderResponse


class OpenAICompatibleObserver:
    provider_id = "openai-compatible"

    def __init__(self, *, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model_id = model
        self.base_url = base_url.rstrip("/")

    def observe(self, image: ImageInput, prompt: str, timeout_seconds: float) -> ProviderResponse:
        data_url = f"data:{image.mime_type};base64,{base64.b64encode(image.content).decode()}"
        return self._post(
            [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
            timeout_seconds,
        )

    def repair(self, invalid_text: str, prompt: str, timeout_seconds: float) -> ProviderResponse:
        return self._post(
            [
                {
                    "type": "text",
                    "text": f"{prompt}\nReformat this data only as valid JSON:\n{invalid_text}",
                }
            ],
            timeout_seconds,
        )

    def _post(self, content: list[dict[str, object]], timeout: float) -> ProviderResponse:
        wire = {
            "model": self.model_id,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0,
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(wire).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                # Some providers front their API with Cloudflare, which blocks the
                # default `Python-urllib/x.y` User-Agent as a bot signature (error
                # code 1010) even with a valid key and payload.
                "User-Agent": "child-agent-api/0.1 (+observer-adapter)",
            },
        )
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - configured trusted endpoint
            payload = json.load(response)
        return ProviderResponse(text=payload["choices"][0]["message"]["content"])
