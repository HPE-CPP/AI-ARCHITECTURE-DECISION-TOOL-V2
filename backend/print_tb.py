import asyncio
import httpx
import traceback

client = httpx.AsyncClient()

async def main():
    try:
        await client.get('http://localhost:8000')
    except Exception as e:
        traceback.print_exc()

asyncio.run(main())
