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
from nemi_ai.components.managers import QdrantManager
from nemi_ai import nemi_manager

class DummyWS:
    async def send_json(self, d):
        s = d.get("status", ""); msg = d.get("message", "")
        if s in ("DONE", "ERROR"): print(f"  [{s:6s}] {msg}")
    async def send_text(self, d): pass
    async def close(self): pass

async def main():
    import_dir = sys.argv[1] if len(sys.argv) > 1 else "/tmp/import_data"

    # Connect to Qdrant
    print("Connecting to Qdrant...")
    qm = QdrantManager()
    client = await qm.connect(host="qdrant", port=6333)
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
    collections = client.get_collections().collections
    for col in collections:
        try:
            count = client.count(collection_name=col.name, exact=True).count
            print(f"  {col.name}: {count} points")
        except Exception as e:
            print(f"  {col.name}: error - {e}")

    client.close()

if __name__ == "__main__":
    asyncio.run(main())
