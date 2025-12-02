import chromadb
import hashlib
import os
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

class Embedding:
    def __init__(self, chunk_size=500, chunk_overlap=50, model_name="text-embedding-3-small", return_format=None, **kwargs):
        print(f"Initializing Embedding with chunk_size={chunk_size}")
        self.chunk_size = chunk_size
        self.client = chromadb.PersistentClient(path="./chroma_db")
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.embedding_function = OpenAIEmbeddingFunction(api_key=api_key, model_name=model_name)
        self.cache_collection = self.client.get_or_create_collection("query_cache", embedding_function=self.embedding_function)
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.return_format = return_format

        print("Embedding initialized successfully")

        # Debug... dump all collections
        collections = self.client.list_collections()
        print("Existing collections in ChromaDB:")
        for coll in collections:
            print(f" - {coll.name} (id: {coll.id})")
            # For each collection, show number of items
            collection = self.client.get_collection(coll.name)
            count = collection.count()
            print(f"   Number of items: {count}")


    def _get_doc_hash(self, doc):
        doc_hash = hashlib.md5(doc.encode()).hexdigest()
        print(f"Document hash: {doc_hash}")
        return doc_hash

    def add(self, doc, update=False):
        print(f"Adding document with chunk_size={self.chunk_size}, update={update}")
        doc_hash = self._get_doc_hash(doc)
        collection_name = f"doc_{doc_hash}"
        
        collection = self.client.get_or_create_collection(collection_name, embedding_function=self.embedding_function)
        num_chunks = collection.count()
        if num_chunks > 0 and not update:
            print(f"Collection already has {num_chunks} chunks")
            print("Document already exists in collection, skipping add")
            return collection
        
        # Split the document
        chunks = self.text_splitter.split_text(doc)
        print(f"Document split into {len(chunks)} chunks")
        
        if len(chunks) == num_chunks and update:
            print(f"Number of chunks same ({num_chunks}), skipping update")
            return collection
        
        print(f"Number of chunks different (old: {num_chunks}, new: {len(chunks)}), updating")
        self.client.delete_collection(collection_name)
        collection = self.client.get_or_create_collection(collection_name, embedding_function=self.embedding_function)
        
        print("Adding chunks to collection")
        collection.add(
            documents=chunks,
            ids=[f"chunk_{i}" for i in range(len(chunks))]
        )
        print("Document added to collection")

        return collection

    def query(self, query_text, doc):
        print(f"Querying with text: '{query_text}'")
        collection = self.add(doc, update=True)
        
        # Cache query embedding
        query_hash = hashlib.md5(query_text.encode()).hexdigest()
        query_id = f"query_{query_hash}"
        print(f"Query hash: {query_id}")
        #cache_result = self.cache_collection.get(ids=[query_hash])

        cache_result = self.cache_collection.get(ids=[query_id], include=["embeddings"])
        if cache_result['embeddings'].size == 0:
            self.cache_collection.add(documents=[query_text], ids=[query_id])
            cache_result = self.cache_collection.get(ids=[query_id], include=["embeddings"])
        else:
            print("Using cached embedding")
        

        print("Retrieved cached embedding", cache_result)
        embedding = cache_result['embeddings'][0]
        print(f"Embedding: {embedding}")
        
        print("Performing query on collection")
        results = collection.query(
            query_embeddings=[embedding],
            n_results=5
        )
        documents = results['documents'][0]
        print(f"Query returned {len(documents)} results")

        if self.return_format is None:
            return documents
        elif self.return_format == "text":
            if len(documents) == 0:
                return "(empty)"
            return "----\n".join(documents)
        elif self.return_format == "json":
            return json.dumps(documents, indent=2)
        else:
            raise ValueError(f"Unknown format: {self.return_format}")