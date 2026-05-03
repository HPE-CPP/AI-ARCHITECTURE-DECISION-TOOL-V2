"""
smart_chat.py — Real AI Chat: Web Search + LLM Thinking
=========================================================
The chatbot genuinely thinks by:
1. Searching DuckDuckGo Instant Answer API (no API key needed)
2. Fetching Wikipedia summaries for technical topics
3. Injecting web results + analysis context into LLM prompt
4. LLM synthesises a real, personalised answer
5. Smart rich fallback when LLM is unavailable

This answers ANY question — architecture, implementation, cost,
latest papers, debugging, comparisons — not just a fixed list.
"""
from __future__ import annotations
import asyncio
import logging
import re
import urllib.parse
from typing import Optional, Any
import httpx

logger = logging.getLogger(__name__)

SEARCH_TIMEOUT = 5
LLM_TIMEOUT = 20


# ── Web search (DuckDuckGo Instant Answer — no API key) ──────────────────────
async def _ddg_search(query: str) -> str:
    """DuckDuckGo Instant Answer API — returns plain text summary."""
    try:
        encoded = urllib.parse.quote_plus(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            r = await client.get(url, headers={"User-Agent": "ArchGuide-Research/1.0"})
            if r.status_code != 200:
                return ""
            data = r.json()
            parts = []
            abstract = data.get("AbstractText", "").strip()
            if abstract:
                parts.append(abstract[:800])
            for topic in (data.get("RelatedTopics") or [])[:3]:
                text = topic.get("Text", "").strip() if isinstance(topic, dict) else ""
                if text:
                    parts.append(text[:300])
            answer = data.get("Answer", "").strip()
            if answer:
                parts.insert(0, f"Direct answer: {answer}")
            return "\n".join(parts)[:1500]
    except Exception as e:
        logger.debug(f"DDG search failed: {e}")
        return ""


async def _wiki_summary(topic: str) -> str:
    """Wikipedia REST API summary — no API key, fast, reliable."""
    try:
        slug = topic.replace(" ", "_")
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(slug)}"
        async with httpx.AsyncClient(timeout=SEARCH_TIMEOUT) as client:
            r = await client.get(url, headers={"User-Agent": "ArchGuide-Research/1.0"})
            if r.status_code != 200:
                return ""
            data = r.json()
            extract = data.get("extract", "").strip()
            return extract[:1200] if extract else ""
    except Exception:
        return ""


TOPIC_WIKI: dict[str, str] = {
    "rag":        "Retrieval-augmented generation",
    "finetuning": "Fine-tuning (machine learning)",
    "lora":       "Fine-tuning (machine learning)",
    "vector_db":  "Vector database",
    "embedding":  "Word embedding",
    "transformer": "Transformer (deep learning architecture)",
    "cag":        "Large language model",
    "hybrid":     "Ensemble learning",
}


def _detect_topic(message: str) -> str:
    m = message.lower()
    if any(w in m for w in ["rag", "retrieval-augment", "retrieval augment", "vector retriev"]): return "rag"
    if any(w in m for w in ["fine-tun", "finetun", "lora", "qlora", "sft", "rlhf", "training data"]): return "finetuning"
    if any(w in m for w in ["cag", "context augment", "context window"]): return "cag"
    if any(w in m for w in ["hybrid", "combin", "both rag", "rag + fine"]): return "hybrid"
    if any(w in m for w in ["vector db", "vectordb", "pinecone", "chroma", "weaviate", "qdrant", "faiss"]): return "vector_db"
    if any(w in m for w in ["embed", "semantic search", "embedding model", "nomic", "ada"]): return "embedding"
    if any(w in m for w in ["lora", "qlora", "adapter", "peft", "rank"]): return "lora"
    if any(w in m for w in ["transform", "attention mechanism", "bert ", " gpt", "llm", "language model"]): return "transformer"
    if any(w in m for w in ["cost", "price", "budget", "expensive", "cheap", "monthly cost", "annual cost"]): return "cost"
    if any(w in m for w in ["latency", "speed", "fast", "slow", "response time", " ms", "millisecond"]): return "latency"
    if any(w in m for w in ["implement", "how to build", "step by step", "deploy", "production"]): return "implementation"
    if any(w in m for w in ["risk", "danger", "problem", "limitation", "weakness", "fail"]): return "risk"
    return "general"


async def _fetch_web_context(topic: str, message: str) -> tuple[str, bool]:
    """
    Fetch web context: tries DDG search + Wikipedia in parallel.
    Returns (context_text, web_was_browsed).
    """
    ddg_query = f"{message[:120]} AI architecture LLM"
    wiki_topic = TOPIC_WIKI.get(topic, "")

    tasks = [_ddg_search(ddg_query)]
    if wiki_topic:
        tasks.append(_wiki_summary(wiki_topic))

    try:
        results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=6.0
        )
    except asyncio.TimeoutError:
        return "", False

    parts = []
    for r in results:
        if isinstance(r, str) and r.strip():
            parts.append(r.strip())

    combined = "\n\n".join(parts)
    return combined[:2000], bool(combined.strip())


def _build_system_prompt(analysis: Optional[dict]) -> str:
    base = (
        "You are ArchGuide's Senior AI Architecture Expert with deep knowledge in RAG, "
        "Fine-Tuning, CAG, Hybrid architectures, LLM infrastructure, vector databases, "
        "embedding models, LoRA, vLLM, and enterprise AI deployment.\n\n"
        "Rules:\n"
        "- Answer ANY question fully and precisely\n"
        "- Think step-by-step for complex questions\n"
        "- Use **bold** for key terms, bullet points for lists\n"
        "- Give specific numbers, model names, tools\n"
        "- Keep answers under 300 words unless more is genuinely needed\n"
        "- Always be helpful — never refuse a reasonable question"
    )

    if not analysis:
        return base

    rec = analysis.get("recommended", "")
    scores = analysis.get("scores", {})
    conf = round(float(analysis.get("confidence", 0)) * 100)
    signals = analysis.get("signals", {})
    sensitivity = analysis.get("sensitivity", {})
    stable = sensitivity.get("is_stable", True) if sensitivity else True

    score_str = " | ".join(
        f"{k}: {v:.0f}%" for k, v in sorted(scores.items(), key=lambda x: -x[1])
    ) if scores else "N/A"

    key_sigs = []
    for k, v in (signals or {}).items():
        if v and v.get("value"):
            key_sigs.append(f"{k.replace('_',' ')}: {v['value']} ({v.get('confidence',0):.0%})")

    signals_block = "\n".join(f"  • {s}" for s in key_sigs[:8]) or "  • Not extracted"

    ctx = (
        f"\n\n=== USER'S ANALYSIS CONTEXT ===\n"
        f"Recommended: **{rec}** | Confidence: {conf}% | {'Stable ✓' if stable else 'Borderline ⚠'}\n"
        f"Scores: {score_str}\n"
        f"Extracted signals:\n{signals_block}\n"
        f"=== END CONTEXT ===\n\n"
        "When asked 'why', 'explain', or 'what does this mean' — ALWAYS reference the specific "
        "scores, signals, and recommendation above. Make answers personal to this user's analysis."
    )
    return base + ctx


def _build_messages(history: list[dict], user_msg: str, web_ctx: str, system: str) -> list[dict]:
    messages = [{"role": "system", "content": system}]
    if web_ctx:
        messages.append({
            "role": "system",
            "content": f"[LIVE WEB SEARCH RESULTS — use this to give up-to-date answers]\n{web_ctx}"
        })
    for m in history[-14:]:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": str(content)[:600]})
    messages.append({"role": "user", "content": user_msg})
    return messages


async def _call_llm(llm_client: Any, messages: list[dict]) -> str:
    """Try OpenAI direct path first, then Ollama path."""
    # OpenAI direct (best quality)
    if hasattr(llm_client, '_openai_client') and llm_client._openai_client:
        try:
            resp = await asyncio.wait_for(
                llm_client._openai_client.chat.completions.create(
                    model=getattr(llm_client, 'model', 'gpt-4o-mini'),
                    messages=messages,
                    temperature=0.5,
                    max_tokens=500,
                ),
                timeout=LLM_TIMEOUT
            )
            return resp.choices[0].message.content or ""
        except asyncio.TimeoutError:
            logger.warning("OpenAI chat timed out")
        except Exception as e:
            logger.warning(f"OpenAI chat error: {e}")

    # Ollama path — concatenate into single prompt
    if llm_client.provider == "ollama":
        parts = []
        for m in messages:
            r = m["role"]
            c = m["content"]
            if r == "system":
                parts.append(f"[SYSTEM]\n{c}")
            elif r == "user":
                parts.append(f"[USER]\n{c}")
            elif r == "assistant":
                parts.append(f"[ASSISTANT]\n{c}")
        full_prompt = "\n\n".join(parts) + "\n\n[ASSISTANT]\n"
        try:
            answer = await asyncio.wait_for(
                llm_client.generate(
                    prompt=full_prompt,
                    system_prompt="",
                    temperature=0.5,
                    max_tokens=500,
                ),
                timeout=LLM_TIMEOUT
            )
            return answer
        except asyncio.TimeoutError:
            logger.warning(f"Ollama chat timed out after {LLM_TIMEOUT}s")
        except Exception as e:
            logger.warning(f"Ollama chat error: {e}")

    return ""


def _smart_fallback(msg: str, topic: str, analysis: Optional[dict], web_ctx: str) -> str:
    """Rich context-aware fallback when LLM is unavailable."""
    m = msg.lower()
    rec = (analysis or {}).get("recommended", "")
    scores = (analysis or {}).get("scores", {})
    signals = (analysis or {}).get("signals", {})
    conf = round(float((analysis or {}).get("confidence", 0)) * 100)

    # If we got web context, show it usefully
    if web_ctx and len(web_ctx) > 100:
        intro = f"{'Based on your **' + rec + '** analysis and live web search:' if rec else 'Based on live web search:'}\n\n"
        # Format web context nicely
        lines = [l.strip() for l in web_ctx.split("\n") if l.strip()][:8]
        formatted = "\n".join(f"• {l}" if not l.startswith("•") else l for l in lines)
        return intro + formatted + "\n\n*(Connect Ollama or add OPENAI_API_KEY for fuller AI answers)*"

    # Why / reasoning
    if any(w in m for w in ["why", "reason", "explain", "how did", "what drove"]):
        if rec and scores:
            score_line = " | ".join(f"{k}: {v:.0f}%" for k, v in sorted(scores.items(), key=lambda x: -x[1]))
            sigs = [f"{k.replace('_',' ')}: **{v['value']}**" for k, v in signals.items() if v and v.get("value")][:4]
            return (
                f"**{rec}** was recommended because it scored highest across all 10 signals.\n\n"
                f"**Scores:** {score_line}\n\n"
                f"**Key driving factors:**\n" + "\n".join(f"• {s}" for s in sigs) +
                f"\n\n**Confidence: {conf}%** — {'decisive recommendation' if conf >= 75 else 'borderline — consider gathering more requirements'}."
            )

    # Implementation
    if any(w in m for w in ["implement", "how to", "build", "deploy", "step", "start"]):
        steps = {
            "RAG": "1. Choose embedding: `text-embedding-3-small` (OpenAI) or `nomic-embed-text` (free)\n2. Chunk docs: 400-600 tokens, 10% overlap\n3. Index: ChromaDB (local) or Pinecone (managed)\n4. Build chain: query→embed→search→rerank→generate\n5. Monitor: MRR@10 retrieval metric",
            "FineTuning": "1. Collect 1K-10K instruction-response pairs\n2. Choose base: Llama 3.2 or Mistral 7B (free)\n3. Apply LoRA (rank 16-64) with Hugging Face PEFT\n4. Train with TRL or Unsloth (2× faster)\n5. Deploy with vLLM or Ollama",
            "CAG": "1. Choose large-context model: Claude (200K) or GPT-4-Turbo (128K)\n2. Structure knowledge base with clear headers\n3. Pre-load and warm KV cache\n4. Set refresh trigger on knowledge changes\n5. Monitor token usage daily",
            "Hybrid": "1. Fine-tune base model first (follow FT steps)\n2. Build RAG pipeline in parallel (follow RAG steps)\n3. Create query router to classify and route queries\n4. Benchmark both paths independently first\n5. Integrate and run A/B tests",
        }
        return f"**{rec} implementation steps:**\n\n" + steps.get(rec, steps["RAG"])

    # Cost
    if any(w in m for w in ["cost", "price", "budget", "monthly", "expensive"]):
        costs = {
            "RAG": "$170-650/mo (vector DB $50-200 + embeddings $20-50 + LLM inference $100-400). Setup: $500-2K.",
            "FineTuning": "$500-50K upfront training + $50-200/mo inference. Best ROI at high query volume.",
            "CAG": "$0 setup + $2K-5K/mo at scale (full 128K context on every call). Costs scale linearly.",
            "Hybrid": "$3K-15K upfront + $300-900/mo. Only justified at true enterprise scale.",
        }
        all_costs = "\n".join(f"• **{k}:** {v}" for k, v in costs.items())
        primary = f"\n\n**Your recommendation ({rec}):** {costs.get(rec,'')}" if rec else ""
        return f"**Architecture cost comparison (medium scale ~100K queries/month):**\n\n{all_costs}{primary}"

    # Risks
    if any(w in m for w in ["risk", "danger", "limitation", "weakness", "problem", "fail"]):
        risks_map = {
            "RAG": ["Retrieval quality caps answer quality — bad chunks = bad answers", "Latency: 200ms-2s per query", "Context window limits concurrent retrieved chunks"],
            "FineTuning": ["High hallucination risk — no grounding at inference", "Retraining required on every knowledge update", "Catastrophic forgetting can degrade general capabilities"],
            "CAG": ["Hard context window ceiling — KB must fit in model window", "High per-query token cost scales linearly", "Cache goes stale without automated refresh"],
            "Hybrid": ["Most complex system to build and debug", "Dual infrastructure cost", "When answers are wrong, root cause spans both systems"],
        }
        risks = risks_map.get(rec, ["Evaluate architecture-specific risks in the results dashboard"])
        return f"**Top risks for {rec or 'your architecture'}:**\n\n" + "\n".join(f"⚠ {r}" for r in risks) + "\n\n**Mitigation:** Start with benchmarks, monitor key metrics, and have fallback paths designed before production."

    # Compare
    if any(w in m for w in ["compar", "vs", "versus", "differ", "which is better", "trade-off"]):
        s = "\n".join(f"• **{k}:** {v:.0f}%" for k, v in sorted(scores.items(), key=lambda x: -x[1])) if scores else ""
        return (
            f"**Architecture scores for your requirements:**\n{s}\n\n"
            "**Quick comparison:**\n"
            "• **RAG** — Best for dynamic, large-scale KB needing citations\n"
            "• **Fine-Tuning** — Best for static, specialised domains needing speed\n"
            "• **CAG** — Best for small, stable KB needing simplicity\n"
            "• **Hybrid** — Best for enterprise needing max accuracy + freshness\n\n"
            f"Based on your signals, **{rec}** scores best." if rec else ""
        )

    # Generic
    llm_note = "*(Add OPENAI_API_KEY or run Ollama for dynamic AI answers to any question)*"
    return (
        f"I'm your ArchGuide AI assistant{' — your analysis recommended **' + rec + '** (' + str(conf) + '% confidence)' if rec else ''}.\n\n"
        "I can help with:\n"
        "• **Why** this architecture was recommended\n"
        "• **Implementation steps** and technical setup\n"
        "• **Cost estimates** for all 4 architectures\n"
        "• **Risks** and mitigation strategies\n"
        "• **Comparisons** between RAG, Fine-Tuning, CAG, Hybrid\n\n"
        f"Ask me your specific question! {llm_note}"
    )


# ── Main public function ──────────────────────────────────────────────────────
async def generate_chat_response(
    user_message: str,
    analysis_result: Optional[dict] = None,
    history: Optional[list[dict]] = None,
    llm_client: Any = None,
    browse_web: bool = True,
) -> dict:
    """
    Generate a real, dynamic AI response.
    1. Search DuckDuckGo + Wikipedia for fresh context
    2. Build rich LLM prompt with analysis context + web results + history
    3. Call LLM (OpenAI or Ollama) for genuine thinking
    4. Graceful fallback if LLM unavailable
    """
    history = history or []
    topic = _detect_topic(user_message)

    # Fetch web context (parallel with other prep)
    web_ctx = ""
    web_browsed = False
    if browse_web:
        web_ctx, web_browsed = await _fetch_web_context(topic, user_message)

    # Try LLM
    if llm_client:
        try:
            system_prompt = _build_system_prompt(analysis_result)
            messages = _build_messages(history, user_message, web_ctx, system_prompt)
            answer = await _call_llm(llm_client, messages)
            if answer and len(answer.strip()) > 20:
                return {
                    "content": answer.strip(),
                    "source": "llm+web" if web_browsed else "llm",
                    "topic": topic,
                    "web_browsed": web_browsed,
                }
        except Exception as e:
            logger.warning(f"LLM chat pipeline error: {e}")

    # Smart fallback
    fallback = _smart_fallback(user_message, topic, analysis_result, web_ctx)
    return {
        "content": fallback,
        "source": "search+kb" if web_browsed else "kb",
        "topic": topic,
        "web_browsed": web_browsed,
    }
