#!/usr/bin/env python3
"""Import markdown docs into Nemi-AI via WebSocket."""
import asyncio
import json
import os
import base64
import websockets

NEMI_WS = "ws://localhost:8000/ws/import_files"
DOCS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")

CREDENTIALS = {
    "deployment": "Docker",
    "url": "",
    "key": "",
}

RAG_CONFIG_TEMPLATE = {
    "Reader": {
        "selected": "Basic",
        "components": {
            "Basic": {"name": "BasicReader", "config": {}, "available": True, "type": "file"},
        },
    },
    "Chunker": {
        "selected": "Recursive",
        "components": {
            "Recursive": {
                "name": "RecursiveChunker",
                "config": {"Chunk Unit": {"value": 500}, "Chunk Overlap": {"value": 50}},
                "available": True,
                "type": "chunker",
            },
        },
    },
    "Embedder": {
        "selected": "Ollama",
        "components": {
            "Ollama": {
                "name": "Ollama",
                "config": {"Model": {"value": "nomic-embed-text"}},
                "available": True,
                "type": "embedder",
            },
        },
    },
    "Generator": {
        "selected": "OpenAI",
        "components": {
            "OpenAI": {
                "name": "OpenAIGenerator",
                "config": {"Model": {"value": "deepseek-chat"}},
                "available": True,
                "type": "generator",
            },
        },
    },
    "Retriever": {
        "selected": "Window",
        "components": {
            "Window": {
                "name": "WindowRetriever",
                "config": {},
                "available": True,
                "type": "retriever",
            },
        },
    },
}


def make_file_data(filepath):
    with open(filepath, "rb") as f:
        raw = f.read()
    content_b64 = base64.b64encode(raw).decode("ascii")
    filename = os.path.basename(filepath)
    ext = filename.split(".")[-1]
    return {
        "fileID": filename,
        "filename": filename,
        "isURL": False,
        "overwrite": True,
        "extension": ext,
        "source": "",
        "content": content_b64,
        "labels": ["Document"],
        "metadata": "",
        "file_size": len(raw),
        "block": False,
        "status_report": {},
        "status": "READY",
        "rag_config": RAG_CONFIG_TEMPLATE,
    }


async def send_file(ws, file_data):
    data_str = json.dumps(file_data)
    chunk_size = 2000
    total = (len(data_str) + chunk_size - 1) // chunk_size
    for i in range(total):
        chunk = data_str[i * chunk_size : (i + 1) * chunk_size]
        payload = json.dumps({
            "chunk": chunk,
            "isLastChunk": i == total - 1,
            "total": total,
            "order": i,
            "fileID": file_data["fileID"],
            "credentials": CREDENTIALS,
        })
        await ws.send(payload)
        await asyncio.sleep(0.01)
    print(f"  Sent {file_data['filename']} ({total} chunks)")


async def main():
    md_files = []
    for root, dirs, files in os.walk(DOCS_DIR):
        for f in files:
            if f.endswith(".md"):
                md_files.append(os.path.join(root, f))
    md_files.sort()

    if not md_files:
        print("No markdown files found in docs/")
        return

    print(f"Found {len(md_files)} markdown files to import:")
    for f in md_files:
        rel = os.path.relpath(f, DOCS_DIR)
        print(f"  - {rel}")

    print(f"\nConnecting to {NEMI_WS}...")
    async with websockets.connect(NEMI_WS) as ws:
        print("Connected! Sending files...\n")
        for fp in md_files:
            file_data = make_file_data(fp)
            await send_file(ws, file_data)
            await asyncio.sleep(0.5)

        # Wait for responses
        print("\nWaiting for import results (5s)...")
        try:
            async for msg in ws:
                data = json.loads(msg)
                status = data.get("status", "")
                fid = data.get("fileID", "")
                message = data.get("message", "")
                took = data.get("took", 0)
                print(f"  [{status:10s}] {fid} - {message} ({took}s)")
                if status == "DONE" or status == "ERROR":
                    pass
        except asyncio.TimeoutError:
            pass

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
