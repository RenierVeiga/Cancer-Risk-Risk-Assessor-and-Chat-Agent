# Project Rules

## Overview
This repository contains the **NG12 Cancer Risk Assessor**, a Clinical Decision Support application using FastAPI and Google Vertex AI (Gemini 1.5).

## Technology Stack
- **Backend Framework**: FastAPI (Python 3.10+)
- **LLM/Agent**: Gemini 1.5 Pro via `langchain-google-vertexai`
- **Vector Database**: ChromaDB (Local)
- **Embeddings**: HuggingFace `all-MiniLM-L6-v2` (Local) / Vertex AI `text-embedding-004` (Optional)
- **PDF Parsing**: PyMuPDF (`fitz`)

## Development Rules
1. **No External Hallucination**: The Gemini agent MUST strictly use the RAG pipeline to consult the NG12 guidelines. It must not provide medical advice based on its pre-trained knowledge.
2. **Citations**: All assessments must be accompanied by citations extracted from the Chroma vector store.
3. **Environment**: When running the agent, valid Google Cloud Platform credentials must be available in the environment (`gcloud auth application-default login`).
4. **Data Privacy**: The `patients.json` is a mock database. Never commit real PHI (Protected Health Information) to this repository.

## Setup Instructions
- Install dependencies: `pip install -r requirements.txt`
- Build the vector database: `python ingest.py`
- Run the server: `uvicorn main:app --reload`
