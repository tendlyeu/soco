"""XAI/Grok integration wrapper."""
import os
from typing import Optional

from .base import IntegrationBackend


class XaiIntegration(IntegrationBackend):
    """Wraps the OpenAI client pointed at x.ai for content generation."""

    name = "xai"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("XAI_API_KEY", "")
        self.model = model or os.getenv("XAI_MODEL", "grok-3")
        self._client = None

    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def client(self):
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI(api_key=self.api_key, base_url="https://api.x.ai/v1")
        return self._client

    async def generate(
        self,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> str:
        """Generate text using XAI/Grok. Returns the assistant message content."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
