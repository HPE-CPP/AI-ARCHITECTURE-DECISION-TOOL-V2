import asyncio
import json
import logging
from services.signal_extractor import SignalExtractor
from services.llm_client import LLMClient
from services.document_parser import get_relevance_logger

# Configure relevance logger to write to relevance_gate.log
rl = get_relevance_logger()
if not rl.handlers:
    fh = logging.FileHandler("logs/relevance_gate.log")
    rl.addHandler(fh)
    rl.setLevel(logging.INFO)

async def main():
    with open("fraud_doc.txt", "r") as f:
        text = f.read()

    llm = LLMClient()
    extractor = SignalExtractor(llm_client=llm)
    # The extractor takes document_data dict and session_id
    import uuid
    session_id = str(uuid.uuid4())
    signals = await extractor.extract_signals({"full_text": text}, session_id)
    print(json.dumps(signals, indent=2))

if __name__ == "__main__":
    asyncio.run(main())
