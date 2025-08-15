from typing import Any

from openai import OpenAI


class ChatGPTConversation:
    def __init__(self, system_prompt: str = "", model: str = "gpt-4o", temperature: float = 0.0) -> None:
        self.client = OpenAI()
        self.model = model
        self.temperature = temperature

        self.messages: list[dict[str, Any]] = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def send(self, text: str = "", image_url: str = "") -> str:
        parts: list[dict[str, Any]] = []
        if text:
            parts.append({"type": "text", "text": text})
        if image_url:
            parts.append({"type": "image_url", "image_url": {"url": image_url}})
        if not parts:
            raise ValueError("Nothing to send")
        self.messages.append({"role": "user", "content": parts})

        message = (
            self.client.chat.completions.create(
                model=self.model,
                messages=self.messages,
                temperature=self.temperature,
            )
            .choices[0]
            .message
        )

        content: str | None = message.content
        if content is None:
            raise ValueError("OpenAI returned None response")

        self.messages.append({"role": "assistant", "content": content})
        return content
