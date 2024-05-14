from openai import OpenAI


class ChatGPTConversation:
    def __init__(self, system_prompt: str = "", model: str = "gpt-4o", temperature: float = 0.0) -> None:
        self.client = OpenAI()
        self.model = model
        self.temperature = temperature

        self.messages = []
        if system_prompt:
            self.messages.append({"role": "system", "content": system_prompt})

    def send(self, text: str = "", image_url: str = "") -> str:
        parts = []
        if text:
            parts.append({"type": "text", "text": text})
        if image_url:
            parts.append({"type": "image_url", "image_url": {"url": image_url}})
        if not parts:
            raise ValueError("Nothing to send")
        self.messages.append({"role": "user", "content": parts})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=self.temperature,
        ).choices[0].message.content

        self.messages.append({"role": "assistant", "content": response})

        return response
