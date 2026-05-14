"""
LLM Client - Unified interface for OpenAI and Ollama.
Supports dynamic provider switching and structured output.
"""
import asyncio
import json
import logging
from typing import Optional, Any
from openai import AsyncOpenAI
import httpx

from config import settings

logger = logging.getLogger(__name__)

# B-02 FIX: Use a single module-level shared AsyncClient instead of creating a new one
# per LLM call. This enables TCP connection pooling and saves 10-50ms per request.
# Timeout set to 90s (down from 300s) — see B-03 FIX below.
_OLLAMA_TIMEOUT = httpx.Timeout(connect=5.0, read=90.0, write=10.0, pool=5.0)
_ollama_http_client: Optional[httpx.AsyncClient] = None


def get_ollama_http_client() -> httpx.AsyncClient:
    """Return (or lazily create) the shared Ollama HTTP client."""
    global _ollama_http_client
    if _ollama_http_client is None or _ollama_http_client.is_closed:
        _ollama_http_client = httpx.AsyncClient(
            timeout=_OLLAMA_TIMEOUT,
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _ollama_http_client


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
        temperature: float = 0.1,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """Generate completion from the configured LLM provider."""
        import tiktoken
        from fastapi import HTTPException
        
        # AI-002 FIX: Context Window Protection
        # Count tokens and truncate the prompt if it exceeds the model's safe limit.
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            sys_tokens = len(encoding.encode(system_prompt))
            prompt_tokens = len(encoding.encode(prompt))
            total_tokens = sys_tokens + prompt_tokens
            
            # Using 16000 as a safe limit for current typical deployments.
            # If it exceeds, we truncate the prompt text.
            limit = 16000
            if total_tokens > limit:
                allowed_prompt_tokens = limit - sys_tokens - 100 # buffer
                if allowed_prompt_tokens <= 0:
                    raise HTTPException(status_code=413, detail="System prompt alone exceeds token limit.")
                
                # Truncate prompt tokens and decode back to string
                encoded_prompt = encoding.encode(prompt)
                truncated_prompt = encoding.decode(encoded_prompt[:allowed_prompt_tokens])
                prompt = truncated_prompt + "\n\n...[TRUNCATED FOR LENGTH]"
                logger.warning(f"Prompt truncated from {prompt_tokens} to {allowed_prompt_tokens} tokens.")
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            logger.warning(f"Failed to count tokens: {e}")

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
        """Call Ollama local API using the shared HTTP client with a guarded timeout.

        B-02 FIX: Reuse module-level _ollama_http_client for connection pooling.
        B-03 FIX: Wrap in asyncio.wait_for(timeout=90) so a slow GPU/CPU machine
                  cannot starve the entire event loop for up to 5 minutes.
        """
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ]
            options: dict[str, Any] = {
                "temperature": temperature,
                "num_predict": max_tokens,
            }

            payload: dict[str, Any] = {
                "model": settings.OLLAMA_MODEL,
                "messages": messages,
                "stream": False,
                "options": options,
            }
            if json_mode:
                payload["format"] = "json"

            client = get_ollama_http_client()

            # B-03 FIX: asyncio.wait_for enforces a hard timeout at the event-loop level,
            # preventing a stalled Ollama from blocking all concurrent requests.
            async def _do_request() -> str:
                response = await client.post(
                    f"{settings.OLLAMA_BASE_URL}/api/chat",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("message", {}).get("content", "")

            return await asyncio.wait_for(_do_request(), timeout=90.0)

        except asyncio.TimeoutError:
            logger.error("Ollama request timed out after 90s")
            raise RuntimeError("Ollama API call timed out after 90 seconds. Is the model loaded?")
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

    async def generate_json(
        self,
        prompt: str,
        system_prompt: str = "You are an expert AI systems architect. Always respond with valid JSON.",
        temperature: float = 0.0,
    ) -> dict:
        """Generate structured JSON output from LLM."""
        try:
            raw = await self.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                json_mode=True,
            )
        except Exception as e:
            logger.error(f"LLM generate() failed in generate_json: {e}")
            return {"error": f"LLM call failed: {str(e)}"}
        try:
            # Try to extract JSON from the response using robust sanitization
            sanitized = sanitize_json_string(raw)
            return json.loads(sanitized)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse JSON from LLM response: {raw[:200]}")
            return {"error": "Failed to parse LLM response as JSON", "raw": raw}

    def switch_provider(self, provider: str) -> None:
        """Switch LLM provider at runtime (e.g. from ollama ↔ openai).

        This was previously dead code — indented inside sanitize_json_string
        after a return statement and thus completely unreachable.
        """
        self.provider = provider.lower()
        if self.provider == "openai" and not self._openai_client and settings.OPENAI_API_KEY:
            self._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


def sanitize_json_string(raw: str) -> str:
    """Robustly extract JSON from noisy LLM output.
    
    Handles prepended text, markdown formatting, and trailing text.
    """
    if not raw:
        return ""
        
    raw = raw.strip()
    
    # Check for markdown code block markers
    if "```" in raw:
        # Extract the content between the first and last ```
        parts = raw.split("```")
        if len(parts) >= 3:
            # The JSON should be in the second part (index 1)
            # Remove "json" language identifier if present
            content = parts[1].strip()
            if content.startswith("json\n"):
                content = content[5:]
            elif content.startswith("json"):
                content = content[4:]
            return content.strip()
            
    # If no markdown blocks, try to find the first { and last }
    start_idx = raw.find('{')
    end_idx = raw.rfind('}')
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        return raw[start_idx:end_idx + 1]
        
    return raw


def get_llm_client(provider: str = None) -> LLMClient:
    """Factory function to create LLM client."""
    return LLMClient(provider=provider)
