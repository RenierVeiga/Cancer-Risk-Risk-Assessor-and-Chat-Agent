import os
import requests
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

PDF_URL = "https://www.nice.org.uk/guidance/ng12/resources/suspected-cancer-recognition-and-referral-pdf-1837268071621"
PDF_PATH = "ng12_guidelines.pdf"
CHROMA_DIR = "./chroma_db"

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

def extract_text_from_pdf(pdf_path: str) -> str:
    """Extracts text from the given PDF using PyMuPDF."""
    print("Extracting text from PDF...")
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    print(f"Extracted {len(text)} characters.")
    return text

def build_vector_store():
    """Parses the PDF, creates chunks, and stores embeddings in Chroma."""
    download_pdf(PDF_URL, PDF_PATH)
    text = extract_text_from_pdf(PDF_PATH)

    # Split the text into manageable chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", " ", ""]
    )
    
    print("Splitting text into chunks...")
    chunks = text_splitter.split_text(text)
    print(f"Created {len(chunks)} chunks.")

    # Using HuggingFaceEmbeddings as a "compatible" embedding model that runs locally
    # without requiring GCP Vertex API quotas or authentication. 
    # To use Vertex AI, swap this with:
    # from langchain_google_vertexai import VertexAIEmbeddings
    # embeddings = VertexAIEmbeddings(model_name="text-embedding-004")
    print("Initializing embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    print("Building Vector Store...")
    # Create Chroma vector store
    vectorstore = Chroma.from_texts(
        texts=chunks,
        embedding=embeddings,
        persist_directory=CHROMA_DIR
    )
    # Chroma persists automatically in newer versions, but we can explicitly call persist if using older ones
    # vectorstore.persist()
    print(f"Vector store successfully built at {CHROMA_DIR}")

if __name__ == "__main__":
    build_vector_store()
