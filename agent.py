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
class MatchedCriteria(BaseModel):
    recommendation_id: str = Field(description="The exact recommendation ID, e.g. 1.1.2 or 1.2.1")
    cancer_site: str = Field(description="The suspected cancer site/type, e.g. 'Lung Cancer' or 'Oesophageal Cancer'")
    guideline_text: str = Field(description="The exact clinical text or criteria of the recommendation from the guideline PDF.")
    matched_symptoms: List[str] = Field(description="The patient symptoms or risk factors that matched this specific recommendation.")
    pathway: str = Field(description="The action pathway indicated, e.g. 'Suspected cancer pathway referral' or 'Direct access chest X-ray'")

class PremiumAssessmentResult(BaseModel):
    """Clinical assessment result containing referral risk status, reasoning, matched rules, citations, and recommended next steps."""
    patient_id: str = Field(description="The ID of the patient being assessed.")
    assessment_status: str = Field(description="The highest urgency level matched: 'Urgent Referral', 'Urgent Investigation', or 'Routine'.")
    primary_suspected_cancer: str = Field(description="The primary suspected cancer type identified, or 'None'.")
    matched_rules: List[MatchedCriteria] = Field(description="List of all individual NICE recommendations that matched this patient.")
    clinical_reasoning: str = Field(description="The detailed clinical reasoning behind the assessment based on patient data and guidelines.")
    recommended_next_steps: str = Field(description="Clear, actionable GP next steps (e.g. Arrange direct-access chest X-ray within 48 hours).")
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
        
        # 2. Extract clinical features and format an optimized RAG query
        symptoms = patient_data.get("symptoms", [])
        age = patient_data.get("age", "Unknown")
        gender = patient_data.get("gender", "Unknown")
        smoking = patient_data.get("smoking_history", "Never Smoked")
        
        # Translate clinical risk factors to map directly to NICE guideline phrases (e.g., "ever smoked")
        smoking_clause = "ever smoked" if smoking in ["Current Smoker", "Ex-Smoker"] else "never smoked"
        
        # Formulate a natural clinical presentation query to maximize semantic similarity in vector search
        symptoms_query = f"Patient aged {age}, {gender.lower()}, {smoking_clause}, presenting with: {', '.join(symptoms)}"
        
        guidelines_str = retrieve_guidelines(symptoms_query)
        
        # 3. Initialize the Vertex AI Gemini model
        llm = ChatVertexAI(model_name="gemini-2.5-flash", project="sound-oasis-283702", temperature=0)
        
        # System prompt instructions
        from langchain_core.messages import SystemMessage, HumanMessage
        
        # System prompt instructions
        with open("PROMPTS.md", "r") as f:
            system_prompt = f.read()

        # Append explicit JSON structure instructions (single braces work perfectly since there is no prompt formatting engine)
        json_instruction = """
        IMPORTANT: Your output must be a single, valid JSON object matching the schema below. Do not wrap it in conversational text, and do not add any markdown blocks unless it is a valid JSON payload.
        
        JSON Schema:
        {
          "patient_id": "The ID of the patient",
          "assessment_status": "Urgent Referral" | "Urgent Investigation" | "Routine",
          "primary_suspected_cancer": "The primary suspected cancer site/type identified, or 'None'",
          "matched_rules": [
            {
              "recommendation_id": "The exact recommendation number (e.g., '1.1.2', '1.2.1')",
              "cancer_site": "The suspected cancer site (e.g., 'Lung Cancer', 'Pancreatic Cancer')",
              "guideline_text": "The exact clinical criteria or recommendation text from the guidelines",
              "matched_symptoms": ["List of symptoms matching the patient's record for this rule"],
              "pathway": "The diagnostic or referral pathway (e.g., 'Suspected cancer pathway referral', 'Direct access chest X-ray')"
            }
          ],
          "clinical_reasoning": "The detailed clinical reasoning behind the assessment based on patient symptoms, risk factors, and NICE guidelines",
          "recommended_next_steps": "Clear, actionable GP next steps (e.g. Arrange direct-access chest X-ray within 48 hours)",
          "citations": ["Exact excerpts, sentences, or specific section/criteria numbers from the NICE guidelines supporting this decision"]
        }
        """
        
        messages = [
            SystemMessage(content=system_prompt + "\n" + json_instruction),
            HumanMessage(content=f"Please perform the clinical cancer risk assessment based on the following patient data and retrieved NICE cancer guidelines.\n\n### Patient Data:\n{json.dumps(patient_data, indent=2)}\n\n### Retrieved NICE Cancer Guidelines:\n{guidelines_str}")
        ]
        
        response = llm.invoke(messages)
        
        # Clean response text (strip markdown ```json block if present)
        response_text = response.content.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()
        
        # Parse and validate using Pydantic
        parsed_data = json.loads(response_text)
        validated_result = PremiumAssessmentResult(**parsed_data)
        
        return validated_result.dict()
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"error": str(e), "message": "Failed to run assessment. Ensure you have GCP credentials active (e.g., gcloud auth application-default login) and Vertex AI API enabled."}
