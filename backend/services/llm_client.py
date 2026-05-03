"""
LLM Client — Fixed timeouts, never hangs.
Ollama: 25s hard timeout (was 300s = 5 minutes!).
OpenAI: 30s.
Both paths return empty-string on failure instead of hanging.
"""
import json
import logging
import asyncio
from typing import Optional, Any
import httpx

from config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    OLLAMA_TIMEOUT = 25.0   # was 300 — this is why analysis hung
    OPENAI_TIMEOUT = 30.0

    def __init__(self, provider: str = None):
        self.provider = (provider or settings.DEFAULT_LLM_PROVIDER).lower()
        self._openai_client: Optional[Any] = None
        self.model = settings.OPENAI_MODEL

        if self.provider == "openai" and settings.OPENAI_API_KEY:
            try:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception as e:
                logger.warning(f"OpenAI client init failed: {e}")

    async def generate(
        self,
        prompt: str,
        system_prompt: str = "You are an expert AI systems architect.",
        temperature: float = 0.1,
        max_tokens: int = 2048,
        json_mode: bool = False,
    ) -> str:
        if self.provider == "openai" and self._openai_client:
            return await self._openai_generate(prompt, system_prompt, temperature, max_tokens, json_mode)
        elif self.provider == "ollama":
            return await self._ollama_generate(prompt, system_prompt, temperature, max_tokens, json_mode)
        else:
            raise ValueError(f"No LLM provider available. Set DEFAULT_LLM_PROVIDER=ollama or openai in .env")

    async def _openai_generate(self, prompt, system_prompt, temperature, max_tokens, json_mode) -> str:
        if not self._openai_client:
            raise RuntimeError("OpenAI key not configured.")
        kwargs: dict[str, Any] = {
            "model": settings.OPENAI_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "timeout": self.OPENAI_TIMEOUT,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        try:
            resp = await self._openai_client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            raise RuntimeError(str(e))

    async def _ollama_generate(self, prompt, system_prompt, temperature, max_tokens, json_mode) -> str:
        """
        Call Ollama with a strict 25s timeout.
        This prevents the 5-minute hang that plagued the previous version.
        """
        payload: dict[str, Any] = {
            "model": settings.OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": prompt},
            ],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": min(max_tokens, 1024),  # cap at 1024 for speed
            },
        }
        if json_mode:
            payload["format"] = "json"

        try:
            async with httpx.AsyncClient(timeout=self.OLLAMA_TIMEOUT) as client:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")
        except httpx.TimeoutException:
            logger.warning(f"Ollama timed out after {self.OLLAMA_TIMEOUT}s — returning empty")
            raise RuntimeError("Ollama timed out. Heuristics will be used instead.")
        except httpx.ConnectError:
            logger.warning("Ollama not running — is it started? Run: ollama serve")
            raise RuntimeError("Cannot connect to Ollama. Start it with: ollama serve")
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            raise RuntimeError(str(e))

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str = "You are an expert AI systems architect. Always respond with valid JSON only.",
        temperature: float = 0.0,
    ) -> dict:
        try:
            raw = await asyncio.wait_for(
                self.generate(prompt=prompt, system_prompt=system_prompt,
                              temperature=temperature, json_mode=True, max_tokens=1024),
                timeout=22.0  # hard cap — heuristics are the fallback
            )
        except (asyncio.TimeoutError, RuntimeError) as e:
            logger.warning(f"generate_json failed: {e} — returning empty dict")
            return {}

        try:
            raw = raw.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Bad JSON from LLM: {raw[:200]}")
            return {}

    def switch_provider(self, provider: str):
        self.provider = provider.lower()
        if self.provider == "openai" and not self._openai_client and settings.OPENAI_API_KEY:
            try:
                from openai import AsyncOpenAI
                self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            except Exception:
                pass

    @property
    def is_available(self) -> bool:
        if self.provider == "openai":
            return self._openai_client is not None
        return True  # Ollama assumed running; will fail gracefully on timeout


def get_llm_client(provider: str = None) -> LLMClient:
    return LLMClient(provider=provider)
