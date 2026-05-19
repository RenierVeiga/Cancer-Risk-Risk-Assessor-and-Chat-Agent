import os
import requests
import fitz  # PyMuPDF
import chromadb
from chromadb.utils import embedding_functions
from pydantic import BaseModel, Field

PDF_URL = "https://www.nice.org.uk/guidance/ng12/resources/suspected-cancer-recognition-and-referral-pdf-1837268071621"
PDF_PATH = "ng12_guidelines.pdf"
CHROMA_DIR = "./chroma_db"


class ChunkMetadata(BaseModel):
    page: int = Field(ge=1)
    chunk_id: str
    source: str = "NG12 PDF"
    section_title: str | None = None
    citation: str
    chunk_index: int = Field(ge=0)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)


class IngestedChunk(BaseModel):
    document: str
    metadata: ChunkMetadata


def extract_section_title(page_text: str) -> str | None:
    """Best-effort extraction of a page heading for citation metadata."""
    for line in page_text.splitlines():
        cleaned = line.strip()
        if cleaned:
            return cleaned[:120]
    return None

def download_pdf(url: str, output_path: str):
    """Downloads the PDF if it doesn't already exist."""
    if not os.path.exists(output_path):
        print(f"Downloading PDF from {url}...")
        response = requests.get(url)
        response.raise_for_status()
        with open(output_path, "wb") as f:
            f.write(response.content)
        print("Download complete.")
    else:
        print("PDF already exists locally.")

def split_text(text: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> list:
    """Splits text into manageable chunks in pure Python."""
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start:start + chunk_size])
        start += (chunk_size - chunk_overlap)
        # Prevent very small chunks at the end
        if start >= len(text) - chunk_overlap:
            break
    return chunks

def build_vector_store():
    """Parses the PDF page-by-page, creates chunks, and stores embeddings in Chroma with metadata."""
    download_pdf(PDF_URL, PDF_PATH)
    
    print("Extracting text from PDF page by page...")
    doc = fitz.open(PDF_PATH)
    print(f"Total pages: {len(doc)}")
    
    chunks = []
    metadatas = []
    ids = []
    
    for page_idx, page in enumerate(doc):
        page_num = page_idx + 1
        page_text = page.get_text()
        if not page_text.strip():
            continue

        section_title = extract_section_title(page_text)
        
        # Split text within this page
        page_chunks = split_text(page_text, chunk_size=800, chunk_overlap=150)
        for chunk_idx, chunk_text in enumerate(page_chunks):
            # Format custom unique chunk ID e.g. ng12_0024_02
            chunk_id = f"ng12_{page_num:04d}_{chunk_idx:02d}"
            citation_text = (
                f"{section_title} — {PDF_PATH} p.{page_num}, chunk {chunk_idx + 1}"
                if section_title
                else f"{PDF_PATH} p.{page_num}, chunk {chunk_idx + 1}"
            )

            chunk = IngestedChunk(
                document=chunk_text,
                metadata=ChunkMetadata(
                    page=page_num,
                    chunk_id=chunk_id,
                    section_title=section_title,
                    citation=citation_text,
                    chunk_index=chunk_idx,
                    page_start=page_num,
                    page_end=page_num,
                )
            )

            chunks.append(chunk.document)
            metadatas.append(chunk.metadata.model_dump())
            ids.append(chunk_id)

    print(f"Created {len(chunks)} chunks with page metadata.")
    
    print("Initializing embedding model and Persistent Chroma Client...")
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    
    # Use native sentence-transformer embedding function
    sentence_transformer_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    
    # Create or get collection
    collection = client.get_or_create_collection(
        name="ng12_collection",
        embedding_function=sentence_transformer_ef
    )

    print("Building Vector Store...")
    # Add chunks with unique IDs and rich page metadata
    collection.add(
        documents=chunks,
        metadatas=metadatas,
        ids=ids
    )
    print(f"Vector store successfully built at {CHROMA_DIR}")

if __name__ == "__main__":
    build_vector_store()
