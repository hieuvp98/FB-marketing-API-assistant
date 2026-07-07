#!/usr/bin/env python3
"""Test full chat flow: query + generate stream via WebSocket."""
import json, sys, os
sys.path.insert(0, "/app")
import asyncio
import httpx

API = "http://localhost:8000"

async def main():
    # Step 1: Get RAG config
    async with httpx.AsyncClient() as http:
        resp = await http.post(f"{API}/api/get_rag_config",
            json={"deployment": "Docker", "url": "", "key": ""},
            headers={"Origin": API})
        rag = resp.json()["rag_config"]
    print(f"Generator: {rag['Generator']['selected']}")
    print(f"Model: {rag['Generator']['components']['OpenAI']['config']}")

    # Step 2: Query
    async with httpx.AsyncClient() as http:
        resp = await http.post(f"{API}/api/query",
            json={"query": "Facebook API error code 960 timeout", "RAG": rag,
                  "labels": [], "documentFilter": [],
                  "credentials": {"deployment": "Docker", "url": "", "key": ""}},
            headers={"Origin": API})
        result = resp.json()
        ctx = result.get("context", "")
        print(f"\nQuery OK. Context: {len(ctx)} chars")

    # Step 3: Generate via WebSocket
    import json as j
    import websockets
    async with websockets.connect(f"ws://localhost:8000/ws/generate_stream") as ws:
        gen_payload = {
            "query": "Facebook API error code 960 timeout",
            "context": ctx,
            "conversation": [],
            "rag_config": rag,
        }
        await ws.send(j.dumps(gen_payload))
        full = ""
        async for msg in ws:
            data = j.loads(msg)
            chunk = data.get("message", "")
            finish = data.get("finish_reason")
            full += chunk
            if finish == "stop":
                break
        print(f"\nGenerated response ({len(full)} chars):")
        print("─" * 50)
        print(full[:1000])
        print("─" * 50)

if __name__ == "__main__":
    asyncio.run(main())
