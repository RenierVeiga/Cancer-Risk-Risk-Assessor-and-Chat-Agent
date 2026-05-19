import json
import os
from typing import List

import requests
from pydantic import BaseModel, Field, ValidationError

CHROMA_URL = os.environ.get("CHROMA_URL", "http://chroma:8001/search")
PATIENTS_FILE = "patients.json"


class PatientRecord(BaseModel):
    patient_id: str
    name: str
    age: int = Field(ge=0)
    gender: str
    smoking_history: str
    symptoms: List[str] = Field(default_factory=list)
    symptom_duration_days: int = Field(ge=0)


class GuidelineMatch(BaseModel):
    chunk_id: str
    document: str
    page: int = Field(ge=1)
    source: str
    citation: str | None = None
    section_title: str | None = None
    chunk_index: int | None = None
    page_start: int | None = None
    page_end: int | None = None


class GuidelineSearchResponse(BaseModel):
    results: List[GuidelineMatch] = Field(default_factory=list)

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
            if patient.get("patient_id") == patient_id:
                validated_patient = PatientRecord.model_validate(patient)
                return validated_patient.model_dump_json()
                
        return json.dumps({"error": f"Patient with ID {patient_id} not found."})
    except ValidationError as e:
        return json.dumps({"error": f"Invalid patient record: {e}"})
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
    try:
        matches = search_guidelines_structured(query)
        if isinstance(matches, str):
            structured = json.loads(matches)
            if "error" in structured:
                return structured["error"]
            matches = GuidelineSearchResponse.model_validate(structured).results

        if not matches:
            return "No relevant guidelines found."

        excerpts = []
        for i, match in enumerate(matches):
            chunk_id = match.get("chunk_id", "N/A")
            page = match.get("page", "N/A")
            doc = match.get("document", "")
            excerpts.append(f"Guideline Excerpt {i+1} [ID: {chunk_id}, Page: {page}]:\n{doc}")

        return "\n\n".join(excerpts)
    except Exception as e:
        return f"Error communicating with vector store service: {str(e)}"

def search_guidelines_structured(query: str) -> str:
    """
    Searches the NG12 guidelines vector store and returns the raw structured
    response as JSON so callers can render citations with source metadata.

    Args:
        query: The search query, typically the patient's symptoms or conditions.

    Returns:
        A JSON string containing the vector search response or an error payload.
    """
    try:
        response = requests.post(CHROMA_URL, json={"query": query, "k": 3}, timeout=10)
        if response.status_code == 200:
            return GuidelineSearchResponse.model_validate(response.json()).model_dump_json()
        return json.dumps({"error": f"Error from vector service: {response.text}"})
    except ValidationError as e:
        return json.dumps({"error": f"Invalid vector response: {str(e)}"})
    except Exception as e:
        return json.dumps({"error": f"Error communicating with vector store service: {str(e)}"})
