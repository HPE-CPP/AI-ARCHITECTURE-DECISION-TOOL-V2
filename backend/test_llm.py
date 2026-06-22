import sys
import asyncio
sys.path.insert(0, '.')
from services.document_parser import llm_relevance_review
from services.llm_client import get_llm_client

async def main():
    llm = get_llm_client("ollama")
    text = open('long.txt').read()
    res = await llm_relevance_review(text, llm)
    print(res)

asyncio.run(main())
