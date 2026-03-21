"""
LLM Client - Unified interface for OpenAI and Ollama.
Supports dynamic provider switching and structured output.
"""
import json
import logging
from typing import Optional, Any
from openai import AsyncOpenAI
import ollama as ollama_client
import httpx

from config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Unified LLM client supporting OpenAI and Ollama with async calls."""

    def __init__(self, provider: str = "openai"):
        self.provider = provider.lower()
        self._openai_client: Optional[AsyncOpenAI] = None

        if self.provider == "openai" and settings.OPENAI_API_KEY:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are an expert AI systems architect.",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """Generate completion from the configured LLM provider."""
        if self.provider == "openai":
            return await self._openai_generate(prompt, system_prompt, temperature, max_tokens, json_mode)
        elif self.provider == "ollama":
            return await self._ollama_generate(prompt, system_prompt, temperature, max_tokens, json_mode)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    async def _openai_generate(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int, json_mode: bool
    ) -> str:
        """Call OpenAI API."""
        if not self._openai_client:
            raise RuntimeError("OpenAI API key not configured. Set OPENAI_API_KEY in .env")

        kwargs: dict[str, Any] = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await self._openai_client.chat.completions.create(**kwargs)
            content = response.choices[0].message.content
            return content or ""
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise RuntimeError(f"OpenAI API call failed: {str(e)}")

    async def _ollama_generate(
        self, prompt: str, system_prompt: str, temperature: float, max_tokens: int, json_mode: bool
    ) -> str:
        """Call Ollama local API."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            options: dict[str, Any] = {
                "temperature": temperature,
                "num_predict": max_tokens,
            }

            # Use httpx for async call to Ollama
            async with httpx.AsyncClient(timeout=120.0) as client:
                payload = {
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": options,
                }
                if json_mode:
                    payload["format"] = "json"

                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise RuntimeError(f"Ollama API call failed: {str(e)}")

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str = "You are an expert AI systems architect. Always respond with valid JSON.",
        temperature: float = 0.0,
    ) -> dict:
        """Generate structured JSON output from LLM."""
        raw = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            json_mode=True,
        )
        try:
            # Try to extract JSON from the response
            raw = raw.strip()
            if raw.startswith("```"):
                # Remove markdown code fences
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from LLM response: {raw[:200]}")
            return {"error": "Failed to parse LLM response as JSON", "raw": raw}

    def switch_provider(self, provider: str):
        """Switch LLM provider at runtime."""
        self.provider = provider.lower()
        if self.provider == "openai" and not self._openai_client and settings.OPENAI_API_KEY:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def get_llm_client(provider: str = "openai") -> LLMClient:
    """Factory function to create LLM client."""
    return LLMClient(provider=provider)
