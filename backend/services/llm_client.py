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

    def __init__(self, provider: str = None):
        self.provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()
        self._openai_client: Optional[AsyncOpenAI] = None

        if self.provider == "openai" and settings.OPENAI_API_KEY:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are an expert AI systems architect.",
        temperature: float = 0.0,
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

            # Use httpx for async call to Ollama (increased timeout for slower machines/CPUs)
            async with httpx.AsyncClient(timeout=300.0) as client:
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
        except httpx.HTTPError as he:
            err_text = getattr(he, "response", None)
            err_msg = err_text.text if err_text else str(he)
            logger.error(f"Ollama HTTP error: {he!r} - {err_msg}")
            raise RuntimeError(f"Ollama API call failed: {he!r} {err_msg}")
        except Exception as e:
            logger.error(f"Ollama API error: {e!r}")
            raise RuntimeError(f"Ollama API call failed: {e!r}")

    async def generate_chat(
        self,
        messages: list[dict],
        temperature: float = 0.25,
        max_tokens: int = 768,
    ) -> str:
        """Multi-turn chat: accepts a pre-built messages list (system + alternating user/assistant).
        Uses the same Ollama /api/chat endpoint but preserves the full conversation thread
        so the model can track context across turns.
        """
        if self.provider == "openai":
            if not self._openai_client:
                raise RuntimeError("OpenAI API key not configured.")
            try:
                response = await self._openai_client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"OpenAI chat error: {e}")
                raise RuntimeError(f"OpenAI chat failed: {e}")

        # Ollama path
        options: dict[str, Any] = {"temperature": temperature, "num_predict": max_tokens}
        payload: dict[str, Any] = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        client = get_ollama_http_client()

        async def _do_request() -> str:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json=payload,
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "")

        try:
            return await asyncio.wait_for(_do_request(), timeout=90.0)
        except asyncio.TimeoutError:
            raise RuntimeError("Ollama timed out after 90s.")
        except httpx.HTTPError as he:
            err_msg = getattr(he, "response", None)
            raise RuntimeError(f"Ollama HTTP error: {he!r} {err_msg.text if err_msg else ''}")
        except Exception as e:
            raise RuntimeError(f"Ollama chat failed: {e!r}")

    async def stream_chat(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 300,
    ):
        """Stream chat tokens one by one. Yields str tokens as they arrive."""
        if self.provider == "openai":
            if not self._openai_client:
                raise RuntimeError("OpenAI API key not configured.")
            stream = await self._openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            async for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield token
            return

        # Ollama streaming path
        payload: dict[str, Any] = {
            "model": settings.OLLAMA_MODEL,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
        client = get_ollama_http_client()
        try:
            async with client.stream(
                "POST",
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json=payload,
                timeout=httpx.Timeout(connect=5.0, read=90.0, write=10.0, pool=5.0),
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = data.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if data.get("done"):
                        break
        except httpx.HTTPError as he:
            raise RuntimeError(f"Ollama stream error: {he!r}")
        except Exception as e:
            raise RuntimeError(f"Ollama stream failed: {e!r}")

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


def get_llm_client(provider: str = None) -> LLMClient:
    """Factory function to create LLM client."""
    return LLMClient(provider=provider)
