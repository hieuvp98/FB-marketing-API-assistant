"""Main Nemi-AI manager — orchestrates the full RAG pipeline over Qdrant."""

from __future__ import annotations

import asyncio
import hashlib
import importlib
import json
import math
import os
from copy import deepcopy
from datetime import datetime

from dotenv import load_dotenv
from wasabi import msg

from nemi_ai.components.document import Document
from nemi_ai.components.managers import (
    ReaderManager,
    ChunkerManager,
    EmbeddingManager,
    RetrieverManager,
    GeneratorManager,
    QdrantManager,
)
from nemi_ai.server.helpers import LoggerManager
from nemi_ai.server.types import FileConfig, FileStatus, ChunkScore, Credentials

load_dotenv()


class NemiManager:
    """Manages all Nemi-AI Components over Qdrant."""

    def __init__(self) -> None:
        self.reader_manager = ReaderManager()
        self.chunker_manager = ChunkerManager()
        self.embedder_manager = EmbeddingManager()
        self.retriever_manager = RetrieverManager()
        self.generator_manager = GeneratorManager()
        self.qdrant_manager = QdrantManager()
        self.rag_config_uuid = "e0adcc12-9bad-4588-8a1e-bab0af6ed485"
        self.theme_config_uuid = "baab38a7-cb51-4108-acd8-6edeca222820"
        self.user_config_uuid = "f53f7738-08be-4d5a-b003-13eb4bf03ac7"
        self.environment_variables = {}
        self.installed_libraries = {}

        self.verify_installed_libraries()
        self.verify_variables()

    async def connect(
        self, credentials: Credentials, port: str = "6333"
    ) -> QdrantManager:
        """Connect to Qdrant.

        ``port`` is ignored when using deployment='Qdrant' (hosted),
        used as the Qdrant gRPC/HTTP port for 'Docker' / 'Local'.
        Default port 6333 is the Qdrant HTTP port.
        """
        start_time = asyncio.get_event_loop().time()
        try:
            host = credentials.url or os.getenv("QDRANT_HOST", "localhost")
            api_key = credentials.key or os.getenv("QDRANT_API_KEY", "")
            p = int(port or os.getenv("QDRANT_PORT", "6333"))

            client = await self.qdrant_manager.connect(
                host=host, port=p, api_key=api_key
            )
            if client:
                end_time = asyncio.get_event_loop().time()
                msg.info(f"Connection time: {end_time - start_time:.2f} seconds")
                return client
            raise Exception("Failed to connect to Qdrant")
        except Exception as e:
            raise e

    async def disconnect(self, client):
        start_time = asyncio.get_event_loop().time()
        result = await self.qdrant_manager.disconnect(client)
        end_time = asyncio.get_event_loop().time()
        msg.info(f"Disconnection time: {end_time - start_time:.2f} seconds")
        return result

    async def get_deployments(self):
        deployments = {
            "QDRANT_HOST": os.getenv("QDRANT_HOST", "localhost"),
            "QDRANT_PORT": os.getenv("QDRANT_PORT", "6333"),
            "QDRANT_API_KEY": os.getenv("QDRANT_API_KEY", ""),
        }
        return deployments

    # ── Import ───────────────────────────────────────────────────

    async def import_document(
        self, client, fileConfig: FileConfig, logger: LoggerManager = LoggerManager()
    ):
        try:
            loop = asyncio.get_running_loop()
            start_time = loop.time()

            duplicate_uuid = await self.qdrant_manager.exist_document_name(
                client, fileConfig.filename
            )
            if duplicate_uuid is not None and not fileConfig.overwrite:
                raise Exception(f"{fileConfig.filename} already exists in Nemi-AI")
            elif duplicate_uuid is not None and fileConfig.overwrite:
                await self.qdrant_manager.delete_document(client, duplicate_uuid)
                await logger.send_report(
                    fileConfig.fileID,
                    status=FileStatus.STARTING,
                    message=f"Overwriting {fileConfig.filename}",
                    took=0,
                )
            else:
                await logger.send_report(
                    fileConfig.fileID,
                    status=FileStatus.STARTING,
                    message="Starting Import",
                    took=0,
                )

            documents = await self.reader_manager.load(
                fileConfig.rag_config["Reader"].selected, fileConfig, logger
            )

            tasks = [
                self.process_single_document(client, doc, fileConfig, logger)
                for doc in documents
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful_tasks = sum(
                1 for result in results if not isinstance(result, Exception)
            )

            if successful_tasks > 1:
                await logger.send_report(
                    fileConfig.fileID,
                    status=FileStatus.INGESTING,
                    message=f"Imported {fileConfig.filename} and it's {successful_tasks} documents into Qdrant",
                    took=round(loop.time() - start_time, 2),
                )
            elif successful_tasks == 1:
                await logger.send_report(
                    fileConfig.fileID,
                    status=FileStatus.INGESTING,
                    message=f"Imported {fileConfig.filename} and {len(documents[0].chunks)} chunks into Qdrant",
                    took=round(loop.time() - start_time, 2),
                )
            elif (
                successful_tasks == 0
                and len(results) == 1
                and isinstance(results[0], Exception)
            ):
                raise results[0]
            else:
                raise Exception(
                    f"No documents imported {successful_tasks} of {len(results)} succesful tasks"
                )

            await logger.send_report(
                fileConfig.fileID,
                status=FileStatus.DONE,
                message=f"Import for {fileConfig.filename} completed successfully",
                took=round(loop.time() - start_time, 2),
            )

        except Exception as e:
            await logger.send_report(
                fileConfig.fileID,
                status=FileStatus.ERROR,
                message=f"Import for {fileConfig.filename} failed: {str(e)}",
                took=0,
            )
            return

    async def process_single_document(
        self,
        client,
        document: Document,
        fileConfig: FileConfig,
        logger: LoggerManager,
    ):
        loop = asyncio.get_running_loop()
        start_time = loop.time()

        if fileConfig.isURL:
            currentFileConfig = deepcopy(fileConfig)
            currentFileConfig.fileID = fileConfig.fileID + document.title
            currentFileConfig.isURL = False
            currentFileConfig.filename = document.title
            await logger.create_new_document(
                fileConfig.fileID + document.title,
                document.title,
                fileConfig.fileID,
            )
        else:
            currentFileConfig = fileConfig

        try:
            duplicate_uuid = await self.qdrant_manager.exist_document_name(
                client, document.title
            )
            if duplicate_uuid is not None and not currentFileConfig.overwrite:
                raise Exception(f"{document.title} already exists in Nemi-AI")
            elif duplicate_uuid is not None and currentFileConfig.overwrite:
                await self.qdrant_manager.delete_document(client, duplicate_uuid)

            chunk_task = asyncio.create_task(
                self.chunker_manager.chunk(
                    currentFileConfig.rag_config["Chunker"].selected,
                    currentFileConfig,
                    [document],
                    self.embedder_manager.embedders[
                        currentFileConfig.rag_config["Embedder"].selected
                    ],
                    logger,
                )
            )
            chunked_documents = await chunk_task

            embedding_task = asyncio.create_task(
                self.embedder_manager.vectorize(
                    currentFileConfig.rag_config["Embedder"].selected,
                    currentFileConfig,
                    chunked_documents,
                    logger,
                )
            )
            vectorized_documents = await embedding_task

            for document in vectorized_documents:
                ingesting_task = asyncio.create_task(
                    self.qdrant_manager.import_document(
                        client,
                        document,
                        currentFileConfig.rag_config["Embedder"]
                        .components[fileConfig.rag_config["Embedder"].selected]
                        .config["Model"]
                        .value,
                    )
                )
                await ingesting_task

            await logger.send_report(
                currentFileConfig.fileID,
                status=FileStatus.INGESTING,
                message=f"Imported {currentFileConfig.filename} into Qdrant",
                took=round(loop.time() - start_time, 2),
            )

            await logger.send_report(
                currentFileConfig.fileID,
                status=FileStatus.DONE,
                message=f"Import for {currentFileConfig.filename} completed successfully",
                took=round(loop.time() - start_time, 2),
            )
        except Exception as e:
            await logger.send_report(
                currentFileConfig.fileID,
                status=FileStatus.ERROR,
                message=f"Import for {fileConfig.filename} failed: {str(e)}",
                took=round(loop.time() - start_time, 2),
            )
            raise Exception(f"Import for {fileConfig.filename} failed: {str(e)}")

    # ── Configuration ───────────────────────────────────────────

    def create_config(self) -> dict:
        """Creates the RAG Configuration with available components."""
        available_environments = self.environment_variables
        available_libraries = self.installed_libraries

        readers = self.reader_manager.readers
        reader_config = {
            "components": {
                reader: readers[reader].get_meta(
                    available_environments, available_libraries
                )
                for reader in readers
            },
            "selected": list(readers.values())[0].name,
        }

        chunkers = self.chunker_manager.chunkers
        chunkers_config = {
            "components": {
                chunker: chunkers[chunker].get_meta(
                    available_environments, available_libraries
                )
                for chunker in chunkers
            },
            "selected": list(chunkers.values())[0].name,
        }

        embedders = self.embedder_manager.embedders
        embedder_config = {
            "components": {
                embedder: embedders[embedder].get_meta(
                    available_environments, available_libraries
                )
                for embedder in embedders
            },
            "selected": list(embedders.values())[0].name,
        }

        retrievers = self.retriever_manager.retrievers
        retrievers_config = {
            "components": {
                retriever: retrievers[retriever].get_meta(
                    available_environments, available_libraries
                )
                for retriever in retrievers
            },
            "selected": list(retrievers.values())[0].name,
        }

        generators = self.generator_manager.generators
        generator_config = {
            "components": {
                generator: generators[generator].get_meta(
                    available_environments, available_libraries
                )
                for generator in generators
            },
            "selected": list(generators.values())[0].name,
        }

        return {
            "Reader": reader_config,
            "Chunker": chunkers_config,
            "Embedder": embedder_config,
            "Retriever": retrievers_config,
            "Generator": generator_config,
        }

    def create_user_config(self) -> dict:
        return {"getting_started": False}

    async def set_theme_config(self, client, config: dict):
        await self.qdrant_manager.set_config(client, self.theme_config_uuid, config)

    async def set_rag_config(self, client, config: dict):
        await self.qdrant_manager.set_config(client, self.rag_config_uuid, config)

    async def set_user_config(self, client, config: dict):
        await self.qdrant_manager.set_config(client, self.user_config_uuid, config)

    async def load_rag_config(self, client):
        """Load RAG config from Qdrant, creating default if missing."""
        loaded_config = await self.qdrant_manager.get_config(
            client, self.rag_config_uuid
        )
        new_config = self.create_config()
        if loaded_config is not None:
            if self.verify_config(loaded_config, new_config):
                msg.info("Using Existing RAG Configuration")
                return loaded_config
            else:
                msg.info("Using New RAG Configuration")
                await self.set_rag_config(client, new_config)
                return new_config
        else:
            msg.info("Using New RAG Configuration")
            return new_config

    async def load_theme_config(self, client):
        loaded_config = await self.qdrant_manager.get_config(
            client, self.theme_config_uuid
        )
        if loaded_config is None:
            return None, None
        return loaded_config.get("theme"), loaded_config.get("themes")

    async def load_user_config(self, client):
        loaded_config = await self.qdrant_manager.get_config(
            client, self.user_config_uuid
        )
        if loaded_config is None:
            return self.create_user_config()
        return loaded_config

    def verify_config(self, a: dict, b: dict) -> bool:
        try:
            if os.getenv("NEMI_PRODUCTION") == "Demo":
                return True
            for a_component_key, b_component_key in zip(a, b):
                if a_component_key != b_component_key:
                    msg.fail(
                        f"Config Validation Failed, component name mismatch: {a_component_key} != {b_component_key}"
                    )
                    return False

                a_component = a[a_component_key]["components"]
                b_component = b[b_component_key]["components"]

                if len(a_component) != len(b_component):
                    msg.fail(
                        f"Config Validation Failed, {a_component_key} component count mismatch: {len(a_component)} != {len(b_component)}"
                    )
                    return False

                for a_rag_component_key, b_rag_component_key in zip(
                    a_component, b_component
                ):
                    if a_rag_component_key != b_rag_component_key:
                        msg.fail(
                            f"Config Validation Failed, component name mismatch: {a_rag_component_key} != {b_rag_component_key}"
                        )
                        return False
                    a_rag_component = a_component[a_rag_component_key]
                    b_rag_component = b_component[b_rag_component_key]

                    a_config = a_rag_component["config"]
                    b_config = b_rag_component["config"]

                    if len(a_config) != len(b_config):
                        msg.fail(
                            f"Config Validation Failed, component config count mismatch: {len(a_config)} != {len(b_config)}"
                        )
                        return False

                    for a_config_key, b_config_key in zip(a_config, b_config):
                        if a_config_key != b_config_key:
                            msg.fail(
                                f"Config Validation Failed, component name mismatch: {a_config_key} != {b_config_key}"
                            )
                            return False

                        a_setting = a_config[a_config_key]
                        b_setting = b_config[b_config_key]

                        if a_setting["description"] != b_setting["description"]:
                            msg.fail(
                                f"Config Validation Failed, description mismatch: {a_setting['description']} != {b_setting['description']}"
                            )
                            return False

                        if sorted(a_setting["values"]) != sorted(b_setting["values"]):
                            msg.fail(
                                f"Config Validation Failed, values mismatch: {a_setting['values']} != {b_setting['values']}"
                            )
                            return False

            return True

        except Exception as e:
            msg.fail(f"Config Validation failed: {str(e)}")
            return False

    async def reset_rag_config(self, client):
        msg.info("Resetting RAG Configuration")
        await self.qdrant_manager.reset_config(client, self.rag_config_uuid)

    async def reset_theme_config(self, client):
        msg.info("Resetting Theme Configuration")
        await self.qdrant_manager.reset_config(client, self.theme_config_uuid)

    async def reset_user_config(self, client):
        msg.info("Resetting User Configuration")
        await self.qdrant_manager.reset_config(client, self.user_config_uuid)

    # ── Environment and Libraries ──────────────────────────────

    def verify_installed_libraries(self) -> None:
        reader = [
            lib
            for reader in self.reader_manager.readers
            for lib in self.reader_manager.readers[reader].requires_library
        ]
        chunker = [
            lib
            for chunker in self.chunker_manager.chunkers
            for lib in self.chunker_manager.chunkers[chunker].requires_library
        ]
        embedder = [
            lib
            for embedder in self.embedder_manager.embedders
            for lib in self.embedder_manager.embedders[embedder].requires_library
        ]
        retriever = [
            lib
            for retriever in self.retriever_manager.retrievers
            for lib in self.retriever_manager.retrievers[retriever].requires_library
        ]
        generator = [
            lib
            for generator in self.generator_manager.generators
            for lib in self.generator_manager.generators[generator].requires_library
        ]

        required_libraries = reader + chunker + embedder + retriever + generator
        unique_libraries = set(required_libraries)

        for lib in unique_libraries:
            try:
                importlib.import_module(lib)
                self.installed_libraries[lib] = True
            except Exception:
                self.installed_libraries[lib] = False

    def verify_variables(self) -> None:
        reader = [
            lib
            for reader in self.reader_manager.readers
            for lib in self.reader_manager.readers[reader].requires_env
        ]
        chunker = [
            lib
            for chunker in self.chunker_manager.chunkers
            for lib in self.chunker_manager.chunkers[chunker].requires_env
        ]
        embedder = [
            lib
            for embedder in self.embedder_manager.embedders
            for lib in self.embedder_manager.embedders[embedder].requires_env
        ]
        retriever = [
            lib
            for retriever in self.retriever_manager.retrievers
            for lib in self.retriever_manager.retrievers[retriever].requires_env
        ]
        generator = [
            lib
            for generator in self.generator_manager.generators
            for lib in self.generator_manager.generators[generator].requires_env
        ]

        required_envs = reader + chunker + embedder + retriever + generator
        unique_envs = set(required_envs)

        for env in unique_envs:
            self.environment_variables[env] = bool(os.environ.get(env))

    # ── Document Content Retrieval ─────────────────────────────

    async def get_content(
        self,
        client,
        uuid: str,
        page: int,
        chunkScores: list[ChunkScore],
    ):
        chunks_per_page = 10
        content_pieces = []
        total_batches = 0

        if len(chunkScores) > 0:
            if page > len(chunkScores):
                page = 0

            total_batches = len(chunkScores)
            chunk = await self.qdrant_manager.get_chunk(
                client, chunkScores[page].uuid, chunkScores[page].embedder
            )

            before_ids = [
                i
                for i in range(
                    max(0, chunkScores[page].chunk_id - int(chunks_per_page / 2)),
                    chunkScores[page].chunk_id,
                )
            ]
            if before_ids:
                chunks_before_chunk = await self.qdrant_manager.get_chunk_by_ids(
                    client,
                    chunkScores[page].embedder,
                    uuid,
                    ids=[
                        i
                        for i in range(
                            max(
                                0, chunkScores[page].chunk_id - int(chunks_per_page / 2)
                            ),
                            chunkScores[page].chunk_id,
                        )
                    ],
                )
                before_content = "".join(
                    [
                        chunk.payload.get("content_without_overlap", "")
                        for chunk in chunks_before_chunk
                    ]
                )
            else:
                before_content = ""

            after_ids = [
                i
                for i in range(
                    chunkScores[page].chunk_id + 1,
                    chunkScores[page].chunk_id + int(chunks_per_page / 2),
                )
            ]
            if after_ids:
                chunks_after_chunk = await self.qdrant_manager.get_chunk_by_ids(
                    client,
                    chunkScores[page].embedder,
                    uuid,
                    ids=[
                        i
                        for i in range(
                            chunkScores[page].chunk_id + 1,
                            chunkScores[page].chunk_id + int(chunks_per_page / 2),
                        )
                    ],
                )
                after_content = "".join(
                    [
                        chunk.payload.get("content_without_overlap", "")
                        for chunk in chunks_after_chunk
                    ]
                )
            else:
                after_content = ""

            content_pieces.append(
                {
                    "content": before_content,
                    "chunk_id": 0,
                    "score": 0,
                    "type": "text",
                }
            )
            if chunk:
                content_pieces.append(
                    {
                        "content": chunk.get("content_without_overlap", ""),
                        "chunk_id": chunkScores[page].chunk_id,
                        "score": chunkScores[page].score,
                        "type": "extract",
                    }
                )
            content_pieces.append(
                {
                    "content": after_content,
                    "chunk_id": 0,
                    "score": 0,
                    "type": "text",
                }
            )

        else:
            document = await self.qdrant_manager.get_document(
                client, uuid, properties=["meta"]
            )
            if not document:
                return ([], 0)
            config = json.loads(document.get("meta", "{}"))
            embedder = config["Embedder"]["config"]["Model"]["value"]
            request_chunk_ids = [
                i
                for i in range(
                    chunks_per_page * (page + 1) - chunks_per_page,
                    chunks_per_page * (page + 1),
                )
            ]

            chunks = await self.qdrant_manager.get_chunk_by_ids(
                client, embedder, uuid, request_chunk_ids
            )

            total_chunks = await self.qdrant_manager.get_chunk_count(
                client, embedder, uuid
            )
            total_batches = int(math.ceil(total_chunks / chunks_per_page))

            content = "".join(
                [chunk.payload.get("content_without_overlap", "") for chunk in chunks]
            )

            content_pieces.append(
                {
                    "content": content,
                    "chunk_id": 0,
                    "score": 0,
                    "type": "text",
                }
            )

        return (content_pieces, total_batches)

    # ── Retrieval Augmented Generation ─────────────────────────

    async def retrieve_chunks(
        self,
        client,
        query: str,
        rag_config: dict,
        labels: list[str] = [],
        document_uuids: list[str] = [],
    ):
        retriever = rag_config["Retriever"].selected
        embedder = rag_config["Embedder"].selected

        await self.qdrant_manager.add_suggestion(client, query)

        vector = await self.embedder_manager.vectorize_query(
            embedder, query, rag_config
        )
        documents, context = await self.retriever_manager.retrieve(
            client,
            retriever,
            query,
            vector,
            rag_config,
            self.qdrant_manager,
            labels,
            document_uuids,
        )

        return (documents, context)

    async def generate_stream_answer(
        self,
        rag_config: dict,
        query: str,
        context: str,
        conversation: list[dict],
    ):
        full_text = ""
        async for result in self.generator_manager.generate_stream(
            rag_config, query, context, conversation
        ):
            full_text += result["message"]
            yield result


class ClientManager:
    def __init__(self) -> None:
        self.clients: dict[str, dict] = {}
        self.manager: NemiManager = NemiManager()
        self.max_time: int = 10
        self.locks: dict[str, asyncio.Lock] = {}

    def hash_credentials(self, credentials: Credentials) -> str:
        cred_string = f"{credentials.deployment}:{credentials.url}:{credentials.key}"
        return hashlib.sha256(cred_string.encode()).hexdigest()

    def get_or_create_lock(self, cred_hash: str) -> asyncio.Lock:
        if cred_hash not in self.locks:
            self.locks[cred_hash] = asyncio.Lock()
        return self.locks[cred_hash]

    def heartbeat(self):
        msg.info(f"{len(self.clients)} clients connected")
        for cred_hash, client in self.clients.items():
            msg.info(f"Client {cred_hash} connected at {client['timestamp']}")

    async def connect(
        self, credentials: Credentials, port: str = "6333"
    ) -> QdrantManager:
        _credentials = credentials

        if not _credentials.url:
            _credentials.url = os.environ.get("QDRANT_HOST", "localhost")
        if not _credentials.key:
            _credentials.key = os.environ.get("QDRANT_API_KEY", "")

        cred_hash = self.hash_credentials(_credentials)

        lock = self.get_or_create_lock(cred_hash)
        async with lock:
            if cred_hash in self.clients:
                msg.info("Found existing Client")
                return self.clients[cred_hash]["client"]
            else:
                msg.warn("Connecting new Client")
                try:
                    client = await self.manager.connect(_credentials, port)
                    if client:
                        self.clients[cred_hash] = {
                            "client": client,
                            "timestamp": datetime.now(),
                        }
                        return client
                    else:
                        raise Exception("Client not created")
                except Exception as e:
                    raise e

    async def disconnect(self):
        msg.warn("Disconnecting Clients!")
        for cred_hash, client in self.clients.items():
            await self.manager.disconnect(client["client"])

    async def clean_up(self):
        msg.info("Cleaning Clients Cache")
        current_time = datetime.now()
        clients_to_remove = []

        for cred_hash, client_data in self.clients.items():
            time_difference = current_time - client_data["timestamp"]
            if time_difference.total_seconds() / 60 > self.max_time:
                clients_to_remove.append(cred_hash)
            client = client_data["client"]

        for cred_hash in clients_to_remove:
            await self.manager.disconnect(self.clients[cred_hash]["client"])
            del self.clients[cred_hash]
            msg.warn(f"Removed client: {cred_hash}")

        msg.info(f"Cleaned up {len(clients_to_remove)} clients")
        self.heartbeat()
