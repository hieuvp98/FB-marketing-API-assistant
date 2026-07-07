"""Orchestration managers for Nemi-AI component pipeline.

Replaces the old monolithic managers.py: WeaviateManager has been moved to
qdrant_manager.py (now QdrantManager). This file keeps the component-level
orchestrators: ReaderManager, ChunkerManager, EmbeddingManager,
RetrieverManager, GeneratorManager.
"""

from __future__ import annotations

import asyncio
import os
from sklearn.decomposition import PCA
from wasabi import msg

# ── QdrantManager is now in its own module ─────────────────────
# Import for convenience; calling code can also import directly.
from nemi_ai.components.qdrant_manager import QdrantManager

from nemi_ai.components.document import Document
from nemi_ai.components.interfaces import (
    Reader,
    Chunker,
    Embedding,
    Retriever,
    Generator,
)
from nemi_ai.server.helpers import LoggerManager
from nemi_ai.server.types import FileConfig, FileStatus

# ── Import Readers ─────────────────────────────────────────────
from nemi_ai.components.reader.BasicReader import BasicReader
from nemi_ai.components.reader.GitReader import GitReader
from nemi_ai.components.reader.UnstructuredAPI import UnstructuredReader
from nemi_ai.components.reader.AssemblyAIAPI import AssemblyAIReader
from nemi_ai.components.reader.HTMLReader import HTMLReader
from nemi_ai.components.reader.FirecrawlReader import FirecrawlReader
from nemi_ai.components.reader.UpstageDocumentParse import UpstageDocumentParseReader

# ── Import Chunkers ────────────────────────────────────────────
from nemi_ai.components.chunking.TokenChunker import TokenChunker
from nemi_ai.components.chunking.SentenceChunker import SentenceChunker
from nemi_ai.components.chunking.RecursiveChunker import RecursiveChunker
from nemi_ai.components.chunking.HTMLChunker import HTMLChunker
from nemi_ai.components.chunking.MarkdownChunker import MarkdownChunker
from nemi_ai.components.chunking.CodeChunker import CodeChunker
from nemi_ai.components.chunking.JSONChunker import JSONChunker
from nemi_ai.components.chunking.SemanticChunker import SemanticChunker

# ── Import Embedders ───────────────────────────────────────────
from nemi_ai.components.embedding.OpenAIEmbedder import OpenAIEmbedder
from nemi_ai.components.embedding.CohereEmbedder import CohereEmbedder
from nemi_ai.components.embedding.OllamaEmbedder import OllamaEmbedder
from nemi_ai.components.embedding.UpstageEmbedder import UpstageEmbedder
from nemi_ai.components.embedding.WeaviateEmbedder import WeaviateEmbedder
from nemi_ai.components.embedding.VoyageAIEmbedder import VoyageAIEmbedder
from nemi_ai.components.embedding.SentenceTransformersEmbedder import (
    SentenceTransformersEmbedder,
)

# ── Import Retrievers ──────────────────────────────────────────
from nemi_ai.components.retriever.WindowRetriever import WindowRetriever

# ── Import Generators ──────────────────────────────────────────
from nemi_ai.components.generation.CohereGenerator import CohereGenerator
from nemi_ai.components.generation.AnthrophicGenerator import AnthropicGenerator
from nemi_ai.components.generation.OllamaGenerator import OllamaGenerator
from nemi_ai.components.generation.AtlasCloudGenerator import AtlasCloudGenerator
from nemi_ai.components.generation.OpenAIGenerator import OpenAIGenerator
from nemi_ai.components.generation.GroqGenerator import GroqGenerator
from nemi_ai.components.generation.NovitaGenerator import NovitaGenerator
from nemi_ai.components.generation.UpstageGenerator import UpstageGenerator

try:
    import tiktoken
except Exception:
    msg.warn("tiktoken not installed, your base installation might be corrupted.")

### Add new components here ###

production = os.getenv("NEMI_PRODUCTION")
if production != "Production":
    readers = [
        BasicReader(),
        HTMLReader(),
        GitReader(),
        UnstructuredReader(),
        AssemblyAIReader(),
        FirecrawlReader(),
        UpstageDocumentParseReader(),
    ]
    chunkers = [
        TokenChunker(),
        SentenceChunker(),
        RecursiveChunker(),
        SemanticChunker(),
        HTMLChunker(),
        MarkdownChunker(),
        CodeChunker(),
        JSONChunker(),
    ]
    embedders = [
        SentenceTransformersEmbedder(),
        OllamaEmbedder(),
        WeaviateEmbedder(),
        UpstageEmbedder(),
        VoyageAIEmbedder(),
        CohereEmbedder(),
        OpenAIEmbedder(),
    ]
    retrievers = [WindowRetriever()]
    generators = [
        OpenAIGenerator(),
        AtlasCloudGenerator(),
        AnthropicGenerator(),
        CohereGenerator(),
        GroqGenerator(),
        NovitaGenerator(),
        UpstageGenerator(),
    ]
else:
    readers = [
        BasicReader(),
        HTMLReader(),
        GitReader(),
        UnstructuredReader(),
        AssemblyAIReader(),
        FirecrawlReader(),
        UpstageDocumentParseReader(),
    ]
    chunkers = [
        TokenChunker(),
        SentenceChunker(),
        RecursiveChunker(),
        SemanticChunker(),
        HTMLChunker(),
        MarkdownChunker(),
        CodeChunker(),
        JSONChunker(),
    ]
    embedders = [
        SentenceTransformersEmbedder(),
        WeaviateEmbedder(),
        VoyageAIEmbedder(),
        UpstageEmbedder(),
        CohereEmbedder(),
        OpenAIEmbedder(),
    ]
    retrievers = [WindowRetriever()]
    generators = [
        AtlasCloudGenerator(),
        OpenAIGenerator(),
        AnthropicGenerator(),
        CohereGenerator(),
        UpstageGenerator(),
    ]


class ReaderManager:
    def __init__(self):
        self.readers: dict[str, Reader] = {reader.name: reader for reader in readers}

    async def load(
        self, reader: str, fileConfig: FileConfig, logger: LoggerManager
    ) -> list[Document]:
        try:
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            if reader in self.readers:
                config = fileConfig.rag_config["Reader"].components[reader].config
                documents: list[Document] = await self.readers[reader].load(
                    config, fileConfig
                )
                for document in documents:
                    document.meta["Reader"] = (
                        fileConfig.rag_config["Reader"].components[reader].model_dump()
                    )
                elapsed_time = round(loop.time() - start_time, 2)
                if len(documents) == 1:
                    await logger.send_report(
                        fileConfig.fileID,
                        FileStatus.LOADING,
                        f"Loaded {fileConfig.filename}",
                        took=elapsed_time,
                    )
                else:
                    await logger.send_report(
                        fileConfig.fileID,
                        FileStatus.LOADING,
                        f"Loaded {fileConfig.filename} with {len(documents)} documents",
                        took=elapsed_time,
                    )
                await logger.send_report(
                    fileConfig.fileID, FileStatus.CHUNKING, "", took=0
                )
                return documents
            else:
                raise Exception(f"{reader} Reader not found")

        except Exception as e:
            raise Exception(f"Reader {reader} failed with: {str(e)}")


class ChunkerManager:
    def __init__(self):
        self.chunkers: dict[str, Chunker] = {
            chunker.name: chunker for chunker in chunkers
        }

    async def chunk(
        self,
        chunker: str,
        fileConfig: FileConfig,
        documents: list[Document],
        embedder: Embedding,
        logger: LoggerManager,
    ) -> list[Document]:
        try:
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            if chunker in self.chunkers:
                config = fileConfig.rag_config["Chunker"].components[chunker].config
                embedder_config = (
                    fileConfig.rag_config["Embedder"].components[embedder.name].config
                )
                chunked_documents = await self.chunkers[chunker].chunk(
                    config=config,
                    documents=documents,
                    embedder=embedder,
                    embedder_config=embedder_config,
                )
                for chunked_document in chunked_documents:
                    chunked_document.meta["Chunker"] = (
                        fileConfig.rag_config["Chunker"]
                        .components[chunker]
                        .model_dump()
                    )
                elapsed_time = round(loop.time() - start_time, 2)
                if len(documents) == 1:
                    await logger.send_report(
                        fileConfig.fileID,
                        FileStatus.CHUNKING,
                        f"Split {fileConfig.filename} into {len(chunked_documents[0].chunks)} chunks",
                        took=elapsed_time,
                    )
                else:
                    await logger.send_report(
                        fileConfig.fileID,
                        FileStatus.CHUNKING,
                        f"Chunked all {len(chunked_documents)} documents with a total of {sum([len(document.chunks) for document in chunked_documents])} chunks",
                        took=elapsed_time,
                    )

                await logger.send_report(
                    fileConfig.fileID, FileStatus.EMBEDDING, "", took=0
                )
                return chunked_documents
            else:
                raise Exception(f"{chunker} Chunker not found")
        except Exception as e:
            raise e


class EmbeddingManager:
    def __init__(self):
        self.embedders: dict[str, Embedding] = {
            embedder.name: embedder for embedder in embedders
        }

    async def vectorize(
        self,
        embedder: str,
        fileConfig: FileConfig,
        documents: list[Document],
        logger: LoggerManager,
    ) -> list[Document]:
        """Vectorizes chunks in batches"""
        try:
            loop = asyncio.get_running_loop()
            start_time = loop.time()
            if embedder in self.embedders:
                config = fileConfig.rag_config["Embedder"].components[embedder].config

                for document in documents:
                    content = [
                        document.metadata + "\n" + chunk.content
                        for chunk in document.chunks
                    ]
                    embeddings = await self.batch_vectorize(embedder, config, content)

                    if len(embeddings) >= 3:
                        pca = PCA(n_components=3)
                        generated_pca_embeddings = pca.fit_transform(embeddings)
                        pca_embeddings = [
                            pca_.tolist() for pca_ in generated_pca_embeddings
                        ]
                    else:
                        pca_embeddings = [embedding[0:3] for embedding in embeddings]

                    for vector, chunk, pca_ in zip(
                        embeddings, document.chunks, pca_embeddings
                    ):
                        chunk.vector = vector
                        chunk.pca = pca_

                    document.meta["Embedder"] = (
                        fileConfig.rag_config["Embedder"]
                        .components[embedder]
                        .model_dump()
                    )

                elapsed_time = round(loop.time() - start_time, 2)
                await logger.send_report(
                    fileConfig.fileID,
                    FileStatus.EMBEDDING,
                    f"Vectorized all chunks",
                    took=elapsed_time,
                )
                await logger.send_report(
                    fileConfig.fileID, FileStatus.INGESTING, "", took=0
                )
                return documents
            else:
                raise Exception(f"{embedder} Embedder not found")
        except Exception as e:
            raise e

    async def batch_vectorize(
        self, embedder: str, config: dict, content: list[str]
    ) -> list[list[float]]:
        """Vectorize content in batches"""
        try:
            batches = [
                content[i : i + self.embedders[embedder].max_batch_size]
                for i in range(0, len(content), self.embedders[embedder].max_batch_size)
            ]
            msg.info(f"Vectorizing {len(content)} chunks in {len(batches)} batches")
            tasks = [
                self.embedders[embedder].vectorize(config, batch) for batch in batches
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            errors = [r for r in results if isinstance(r, Exception)]
            if errors:
                error_messages = [str(e) for e in errors]
                raise Exception(
                    f"Vectorization failed for some batches: {', '.join(error_messages)}"
                )

            flattened_results = [item for sublist in results for item in sublist]

            if len(flattened_results) != len(content):
                raise Exception(
                    f"Mismatch in vectorization results: expected {len(content)} vectors, got {len(flattened_results)}"
                )

            return flattened_results
        except Exception as e:
            raise Exception(f"Batch vectorization failed: {str(e)}")

    async def vectorize_query(
        self, embedder: str, content: str, rag_config: dict
    ) -> list[float]:
        try:
            if embedder in self.embedders:
                config = rag_config["Embedder"].components[embedder].config
                embeddings = await self.embedders[embedder].vectorize(config, [content])
                return embeddings[0]
            else:
                raise Exception(f"{embedder} Embedder not found")
        except Exception as e:
            raise e


class RetrieverManager:
    def __init__(self):
        self.retrievers: dict[str, Retriever] = {
            retriever.name: retriever for retriever in retrievers
        }

    async def retrieve(
        self,
        client,
        retriever: str,
        query: str,
        vector: list[float],
        rag_config: dict,
        qdrant_manager: QdrantManager,
        labels: list[str],
        document_uuids: list[str],
    ):
        try:
            if retriever not in self.retrievers:
                raise Exception(f"Retriever {retriever} not found")

            embedder_model = (
                rag_config["Embedder"]
                .components[rag_config["Embedder"].selected]
                .config["Model"]
                .value
            )
            config = rag_config["Retriever"].components[retriever].config
            documents, context = await self.retrievers[retriever].retrieve(
                client,
                query,
                vector,
                config,
                qdrant_manager,
                embedder_model,
                labels,
                document_uuids,
            )
            return (documents, context)

        except Exception as e:
            raise e


class GeneratorManager:
    def __init__(self):
        self.generators: dict[str, Generator] = {
            generator.name: generator for generator in generators
        }

    async def generate_stream(self, rag_config, query, context, conversation):
        """Generate a stream of response dicts."""

        generator = rag_config["Generator"].selected
        generator_config = (
            rag_config["Generator"].components[rag_config["Generator"].selected].config
        )

        if generator not in self.generators:
            raise Exception(f"Generator {generator} not found")

        async for result in self.generators[generator].generate_stream(
            generator_config, query, context, conversation
        ):
            yield result

    def truncate_conversation_dicts(
        self, conversation_dicts: list[dict[str, any]], max_tokens: int
    ) -> list[dict[str, any]]:
        """
        Truncate conversation history to fit within max_tokens.
        Keeps the most recent messages.
        """
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        accumulated_tokens = 0
        truncated_conversation_dicts = []

        for item_dict in reversed(conversation_dicts):
            item_tokens = encoding.encode(item_dict["content"], disallowed_special=())

            if accumulated_tokens + len(item_tokens) > max_tokens:
                remaining_space = max_tokens - accumulated_tokens
                truncated_content = encoding.decode(item_tokens[:remaining_space])

                truncated_item_dict = {
                    "type": item_dict["type"],
                    "content": truncated_content,
                    "typewriter": item_dict["typewriter"],
                }

                truncated_conversation_dicts.append(truncated_item_dict)
                break

            truncated_conversation_dicts.append(item_dict)
            accumulated_tokens += len(item_tokens)

        return list(reversed(truncated_conversation_dicts))
