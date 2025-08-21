from typing import Any, cast

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam, ChatCompletionUserMessageParam


class ChatGPTConversation:
    """Async ChatGPT conversation handler."""

    def __init__(self, system_prompt: str = "", model: str = "gpt-4o", temperature: float = 0.0) -> None:
        self.client = AsyncOpenAI()
        self.model = model
        self.temperature = temperature

        self.messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    async def send(self, text: str = "", image_url: str = "") -> str:
        parts: list[dict[str, Any]] = []
        if text:
            parts.append({"type": "text", "text": text})
        if image_url:
            parts.append({"type": "image_url", "image_url": {"url": image_url}})
        if not parts:
            raise ValueError("Nothing to send")
        user_message = cast(ChatCompletionUserMessageParam, {"role": "user", "content": parts})
        self.messages.append(user_message)

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=self.temperature,
        )
        message = response.choices[0].message

        content: str | None = message.content
        if content is None:
            raise ValueError("OpenAI returned None response")

        self.messages.append({"role": "assistant", "content": content})
        return content
