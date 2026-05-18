import json
import os
from typing import Dict, Any, List
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

CHROMA_DIR = "./chroma_db"
PATIENTS_FILE = "patients.json"

def get_patient_data(patient_id: str) -> str:
    """
    Retrieves structured patient data from the mock database (patients.json).
    
    Args:
        patient_id: The ID of the patient (e.g., 'PT-101')
        
    Returns:
        A JSON string representation of the patient's data, or an error message if not found.
    """
    if not os.path.exists(PATIENTS_FILE):
        return json.dumps({"error": f"Database file {PATIENTS_FILE} not found."})
        
    try:
        with open(PATIENTS_FILE, "r") as f:
            patients = json.load(f)
            
        for patient in patients:
            if patient["patient_id"] == patient_id:
                return json.dumps(patient)
                
        return json.dumps({"error": f"Patient with ID {patient_id} not found."})
    except Exception as e:
        return json.dumps({"error": str(e)})

def search_guidelines(query: str) -> str:
    """
    Searches the NG12 guidelines vector store for relevant criteria based on the query (symptoms).
    
    Args:
        query: The search query, typically the patient's symptoms or conditions.
        
    Returns:
        A string containing the concatenated text of the most relevant guideline sections.
    """
    if not os.path.exists(CHROMA_DIR):
        return "Error: Vector database not found. Please run ingest.py first."
        
    try:
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)
        
        # Retrieve the top 3 most relevant chunks
        docs = vectorstore.similarity_search(query, k=3)
        
        if not docs:
            return "No relevant guidelines found for the given query."
            
        # Combine the document texts to return to the agent
        results = [f"Guideline Excerpt {i+1}:\n{doc.page_content}" for i, doc in enumerate(docs)]
        return "\n\n".join(results)
    except Exception as e:
        return f"Error searching vector store: {str(e)}"
