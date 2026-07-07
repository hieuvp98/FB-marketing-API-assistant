"""Embedder using fastembed (ONNX-based, lightweight, no torch needed).

Matches the nemi-gpt pattern: local embedding with sentence-transformers models
via the fastembed library (which uses ONNX Runtime instead of PyTorch).
"""

from nemi_ai.components.interfaces import Embedding
from nemi_ai.components.types import InputConfig

try:
    from fastembed import TextEmbedding

    fastembed_available = True
except Exception:
    TextEmbedding = None  # type: ignore
    fastembed_available = False


# ── Supported models ────────────────────────────────────────────
# Matches fastembed's native model registry.
SUPPORTED_MODELS = [
    "sentence-transformers/all-MiniLM-L6-v2",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "mixedbread-ai/mxbai-embed-large-v1",
    "BAAI/bge-small-en-v1.5",
    "BAAI/bge-base-en-v1.5",
    "jinaai/jina-embeddings-v2-base-en",
    "snowflake/snowflake-arctic-embed-xs",
]

# Default model (small, fast, English)
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class SentenceTransformersEmbedder(Embedding):
    """Local embedding using fastembed (sentence-transformers models via ONNX)."""

    def __init__(self):
        super().__init__()
        self.name = "SentenceTransformers"
        self.requires_library = ["fastembed"]
        self.description = "Embeds and retrieves objects using fastembed"
        self.config = {
            "Model": InputConfig(
                type="dropdown",
                value=DEFAULT_MODEL,
                description="Select a local embedding model",
                values=list(SUPPORTED_MODELS),
            ),
        }

    async def vectorize(self, config: dict, content: list[str]) -> list[float]:
        if not fastembed_available:
            raise Exception(
                "fastembed library is not installed. Run: pip install fastembed"
            )
        try:
            model_name = config.get("Model").value or DEFAULT_MODEL
            model = TextEmbedding(model_name)
            # model.embed() returns a generator of numpy arrays
            embeddings = [emb.tolist() for emb in model.embed(content)]
            return embeddings
        except Exception as e:
            raise Exception(f"Failed to vectorize chunks: {str(e)}")
