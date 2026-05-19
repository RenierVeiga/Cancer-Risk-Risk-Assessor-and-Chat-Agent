import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import chromadb
from chromadb.utils import embedding_functions

app = FastAPI(
    title="ChromaDB Vector Search Service",
    description="Microservice for semantic search on NG12 Cancer Guidelines.",
    version="1.0.0"
)

CHROMA_DIR = "./chroma_db"

class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    k: int = Field(default=3, ge=1, le=10)

class SearchMatch(BaseModel):
    chunk_id: str
    document: str
    page: int
    source: str
    citation: str | None = None
    section_title: str | None = None
    chunk_index: int | None = None
    page_start: int | None = None
    page_end: int | None = None

class SearchResponse(BaseModel):
    results: list[SearchMatch] = Field(default_factory=list)

class HealthResponse(BaseModel):
    status: str

@app.post("/search", response_model=SearchResponse)
def search_guidelines(request: SearchRequest):
    if not os.path.exists(CHROMA_DIR):
        raise HTTPException(status_code=500, detail="Vector database not found. Ensure ingest.py ran successfully.")
        
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        
        # Use native sentence-transformer embedding function
        sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        collection = client.get_or_create_collection(
            name="ng12_collection",
            embedding_function=sentence_transformer_ef
        )
        
        results = collection.query(
            query_texts=[request.query],
            n_results=request.k
        )
        
        # Extract matched results
        ids = results.get("ids", [])[0] if results.get("ids") else []
        documents = results.get("documents", [])[0] if results.get("documents") else []
        metadatas = results.get("metadatas", [])[0] if results.get("metadatas") else []
        
        matches = []
        for i in range(len(documents)):
            chunk_id = ids[i] if i < len(ids) else f"chunk_{i}"
            doc_text = documents[i]
            meta = metadatas[i] if i < len(metadatas) and metadatas[i] else {}
            page_num = meta.get("page", 1)
            source = meta.get("source", "NG12 PDF")
            citation = meta.get("citation")
            section_title = meta.get("section_title")
            chunk_index = meta.get("chunk_index")
            page_start = meta.get("page_start")
            page_end = meta.get("page_end")

            if not citation:
                citation = f"{source} p.{page_num}, chunk {i + 1}"
            if page_start is None:
                page_start = page_num
            if page_end is None:
                page_end = page_num
            
            matches.append(SearchMatch(
                chunk_id=chunk_id,
                document=doc_text,
                page=page_num,
                source=source,
                citation=citation,
                section_title=section_title,
                chunk_index=chunk_index,
                page_start=page_start,
                page_end=page_end,
            ))
            
        return SearchResponse(results=matches)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching vector store: {str(e)}")

@app.get("/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="healthy")
