#!/usr/bin/env python3
"""Import markdown files directly via NemiManager (runs inside Docker)."""
import asyncio
import base64
import json
import os
import sys

sys.path.insert(0, "/app")

from nemi_ai.server.types import FileConfig, FileStatus, Credentials
from nemi_ai.server.helpers import LoggerManager
from nemi_ai.components.managers import WeaviateManager
from nemi_ai import nemi_manager

class DummyWS:
    async def send_json(self, d):
        s = d.get("status", ""); msg = d.get("message", "")
        if s in ("DONE", "ERROR"): print(f"  [{s:6s}] {msg}")
    async def send_text(self, d): pass
    async def close(self): pass

async def main():
    import_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/import_data"

    # Connect to Weaviate
    print("Connecting to Weaviate...")
    wm = WeaviateManager()
    client = await wm.connect_to_docker("weaviate", "8177")
    await client.connect()
    if not await client.is_ready():
        print("Failed to connect to Weaviate")
        return
    print("Connected!")

    # Create NemiManager to get a proper RAG config
    m = nemi_manager.NemiManager()

    # Get a proper RAG config from the manager
    rag_config = m.create_config()
    print(f"\nRAG config loaded:")
    print(f"  Reader: {rag_config['Reader']['selected']}")
    print(f"  Chunker: {rag_config['Chunker']['selected']}")
    print(f"  Embedder: {rag_config['Embedder']['selected']}")
    print(f"  Generator: {rag_config['Generator']['selected']}")

    # Make sure NEMI_CONFIGURATION collection exists
    config_exists = await wm.verify_collection(client, wm.config_collection_name)
    print(f"Config collection ready: {config_exists}")

    # Import files
    md_files = sorted([
        os.path.join(import_dir, f) for f in os.listdir(import_dir) if f.endswith(".md")
    ])
    print(f"\nFound {len(md_files)} files to import\n")

    for fp in md_files:
        fn = os.path.basename(fp)
        print(f"📄 {fn}...", end=" ", flush=True)
        with open(fp, "rb") as f:
            raw = f.read()
        b64 = base64.b64encode(raw).decode("ascii")

        fc = FileConfig(
            fileID=fn,
            filename=fn,
            isURL=False,
            overwrite=True,
            extension="md",
            source="",
            content=b64,
            labels=["Document"],
            rag_config=rag_config,
            file_size=len(raw),
            status=FileStatus.READY,
            metadata="",
            status_report={},
        )
        try:
            await m.import_document(client, fc, LoggerManager(DummyWS()))
            print("✅")
        except Exception as e:
            print(f"❌ {e}")

    # Verify
    print("\n--- Verification ---")
    collections = await client.collections.list_all()
    for name in collections:
        try:
            c = await client.collections.get(name).length()
            print(f"  {name}: {c} objects")
        except Exception as e:
            print(f"  {name}: error - {e}")

    await client.close()

if __name__ == "__main__":
    asyncio.run(main())
