from weaviate import Client
from nemi_ai.components.interfaces import Embedder
from nemi_ai.components.document import Document


class GoogleEmbedder(Embedder):
    """
    GoogleEmbedder for Nemi-AI.
    """

    def __init__(self):
        super().__init__()
        self.name = "GoogleEmbedder"
        self.requires_env = ["GOOGLE_API_KEY"]
        self.description = "Embeds and retrieves objects using Google's text-embedding-preview-0409 model"
        self.vectorizer = "text2vec-palm"

    def embed(
        self,
        documents: list[Document],
        client: Client,
        logging: list[dict],
    ) -> bool:
        """Embed Nemi-AI documents and its chunks to Weaviate
        @parameter: documents : list[Document] - List of Nemi-AI documents
        @parameter: client : Client - Weaviate Client
        @parameter: batch_size : int - Batch Size of Input
        @returns bool - Bool whether the embedding what successful.
        """
        return self.import_data(documents, client, logging)
