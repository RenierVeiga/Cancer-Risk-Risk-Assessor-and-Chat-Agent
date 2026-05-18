import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import json
from pydantic import BaseModel, Field
from typing import List
from langchain_google_vertexai import ChatVertexAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from tools import get_patient_data, search_guidelines

# Define tools for the agent
@tool
def retrieve_patient_data(patient_id: str) -> str:
    """Retrieves structured patient data from the mock database based on their ID."""
    return get_patient_data(patient_id)

@tool
def retrieve_guidelines(symptoms: str) -> str:
    """Searches the NG12 guidelines vector store for relevant criteria based on the patient's symptoms."""
    return search_guidelines(symptoms)

# Define the expected structured output
class AssessmentResult(BaseModel):
    patient_id: str = Field(description="The ID of the patient being assessed.")
    assessment: str = Field(description="The final assessment: either 'Urgent Referral', 'Urgent Investigation', or 'Routine'.")
    reasoning: str = Field(description="The clinical reasoning behind the assessment based on patient data and guidelines.")
    citations: List[str] = Field(description="Specific excerpts or citations from the NG12 guidelines supporting the assessment.")

def run_assessment(patient_id: str) -> dict:
    """
    Runs the agent to assess a patient.
    """
    try:
        # 1. Retrieve patient data (via tool call)
        patient_data_str = retrieve_patient_data(patient_id)
        patient_data = json.loads(patient_data_str)
        
        if "error" in patient_data:
            return {"error": patient_data["error"], "message": patient_data["error"]}
        
        # 2. Extract symptoms to search guidelines (via RAG lookup tool)
        symptoms = patient_data.get("symptoms", [])
        age = patient_data.get("age", "Unknown")
        gender = patient_data.get("gender", "Unknown")
        symptoms_query = f"Patient age {age}, gender {gender}, symptoms: {', '.join(symptoms)}"
        
        guidelines_str = retrieve_guidelines(symptoms_query)
        
        # 3. Initialize the Vertex AI Gemini model
        llm = ChatVertexAI(model_name="gemini-2.5-flash", project="sound-oasis-283702", temperature=0)
        
        # System prompt instructions
        with open("PROMPTS.md", "r") as f:
            system_prompt = f.read()

        # Bind the structured output format
        structured_llm = llm.with_structured_output(AssessmentResult)
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Please perform the clinical cancer risk assessment based on the following patient data and retrieved NICE cancer guidelines.\n\n### Patient Data:\n{patient_data}\n\n### Retrieved NICE Cancer Guidelines:\n{guidelines}")
        ])
        
        chain = prompt | structured_llm
        result = chain.invoke({
            "patient_data": json.dumps(patient_data, indent=2),
            "guidelines": guidelines_str
        })
        
        return result.dict()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "message": "Failed to run assessment. Ensure you have GCP credentials active (e.g., gcloud auth application-default login) and Vertex AI API enabled."}
