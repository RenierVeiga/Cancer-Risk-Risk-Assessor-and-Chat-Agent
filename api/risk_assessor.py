import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

import json
import traceback
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import SystemMessage, HumanMessage
from settings import get_app_settings
from tools import (
    GuidelineMatch,
    GuidelineSearchResponse,
    PatientRecord,
    get_patient_data,
    search_guidelines_structured,
)

# Define the expected structured output
class MatchedCriteria(BaseModel):
    recommendation_id: str = Field(description="The exact recommendation ID, e.g. 1.1.2 or 1.2.1")
    cancer_site: str = Field(description="The suspected cancer site/type, e.g. 'Lung Cancer' or 'Oesophageal Cancer'")
    guideline_text: str = Field(description="The exact clinical text or criteria of the recommendation from the guideline PDF.")
    matched_symptoms: List[str] = Field(description="The patient symptoms or risk factors that matched this specific recommendation.")
    pathway: str = Field(description="The action pathway indicated, e.g. 'Suspected cancer pathway referral' or 'Direct access chest X-ray'")


class Citation(BaseModel):
    source: str
    page: int
    chunk_id: str
    excerpt: str
    citation: str | None = None
    section_title: str | None = None
    chunk_index: int | None = None
    page_start: int | None = None
    page_end: int | None = None

class PremiumAssessmentResult(BaseModel):
    """Clinical assessment result containing referral risk status, reasoning, matched rules, citations, and recommended next steps."""
    patient_id: str = Field(description="The ID of the patient being assessed.")
    assessment_status: Literal["Urgent Referral", "Urgent Investigation", "Routine"] = Field(description="The highest urgency level matched: 'Urgent Referral', 'Urgent Investigation', or 'Routine'.")
    primary_suspected_cancer: str = Field(description="The primary suspected cancer type identified, or 'None'.")
    matched_rules: List[MatchedCriteria] = Field(default_factory=list, description="List of all individual NICE recommendations that matched this patient.")
    clinical_reasoning: str = Field(description="The detailed clinical reasoning behind the assessment based on patient data and guidelines.")
    recommended_next_steps: str = Field(description="Clear, actionable GP next steps (e.g. Arrange direct-access chest X-ray within 48 hours).")
    citations: List[Citation] = Field(default_factory=list, description="Specific excerpts or citations from the NG12 guidelines supporting the assessment.")

def _build_assessor_citations(matches: List[GuidelineMatch], limit: int = 5) -> List[Dict[str, Any]]:
    citations: List[Dict[str, Any]] = []
    seen_chunks = set()

    for i, match in enumerate(matches[:limit]):
        chunk_id = match.chunk_id or f"chunk_{i}"
        if chunk_id in seen_chunks:
            continue
        seen_chunks.add(chunk_id)

        citations.append(Citation(
            source=match.source or "NG12 PDF",
            page=int(match.page or 1),
            chunk_id=chunk_id,
            excerpt=(match.document or "").strip(),
            citation=match.citation or f"{match.source or 'NG12 PDF'} p.{match.page or 1}, chunk {i + 1}",
            section_title=match.section_title,
            chunk_index=match.chunk_index,
            page_start=match.page_start,
            page_end=match.page_end,
        ).model_dump())

    return citations

def _format_guideline_context(matches: List[GuidelineMatch]) -> str:
    if not matches:
        return "No guideline chunks retrieved."

    formatted = []
    for i, match in enumerate(matches):
        page = match.page
        chunk_id = match.chunk_id
        source = match.source
        doc = (match.document or "").strip()
        formatted.append(
            f"[{i+1}] Source: {source} | Page: {page} | Chunk ID: {chunk_id}\n{doc}"
        )

    return "\n\n".join(formatted)


def _load_prompt_file() -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "RISK_ASSESSOR_PROMPT.md")
    if not os.path.exists(prompt_path):
        raise RuntimeError(f"Prompt file not found: {prompt_path}")

    with open(prompt_path, "r", encoding="utf-8") as handle:
        prompt = handle.read().strip()

    if not prompt:
        raise RuntimeError(f"Prompt file is empty: {prompt_path}")

    return prompt

def run_assessment(patient_id: str) -> dict:
    """
    Runs the agent to assess a patient.
    """
    try:
        # 1. Retrieve patient data (via tool call)
        patient_data_str = get_patient_data(patient_id)
        patient_payload = json.loads(patient_data_str)
        
        if "error" in patient_payload:
            return {"error": patient_payload["error"], "message": patient_payload["error"]}

        patient_data = PatientRecord.model_validate(patient_payload)
        
        # 2. Extract clinical features and format an optimized RAG query
        symptoms = patient_data.symptoms
        age = patient_data.age
        gender = patient_data.gender
        smoking = patient_data.smoking_history
        
        # Translate clinical risk factors to map directly to NICE guideline phrases (e.g., "ever smoked")
        smoking_clause = "ever smoked" if smoking in ["Current Smoker", "Ex-Smoker"] else "never smoked"
        
        # Formulate a natural clinical presentation query to maximize semantic similarity in vector search
        symptoms_query = f"Patient aged {age}, {gender.lower()}, {smoking_clause}, presenting with: {', '.join(symptoms)}"
        
        guidelines_response = search_guidelines_structured(symptoms_query)
        guidelines_payload = GuidelineSearchResponse.model_validate_json(guidelines_response)
        guideline_matches = guidelines_payload.results
        guidelines_str = _format_guideline_context(guideline_matches)
        
        # 3. Initialize the Vertex AI Gemini model
        app_settings = get_app_settings()
        llm = ChatVertexAI(
            model_name=app_settings.vertex_ai.model_name,
            project=app_settings.vertex_ai.project,
            temperature=0,
        ).with_structured_output(PremiumAssessmentResult)

        system_prompt = _load_prompt_file()

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Please perform the clinical cancer risk assessment based on the following patient data and retrieved NICE cancer guidelines.\n\n### Patient Data:\n{json.dumps(patient_data.model_dump(), indent=2)}\n\n### Retrieved NICE Cancer Guidelines:\n{guidelines_str}")
        ]
        
        response = llm.invoke(messages)
        validated_result = response if isinstance(response, PremiumAssessmentResult) else PremiumAssessmentResult.model_validate(response)
        result = validated_result.model_dump()
        result["citations"] = _build_assessor_citations(guideline_matches)

        return result
        
    except Exception as e:
        traceback.print_exc()
        return {"error": str(e), "message": "Failed to run assessment. Ensure you have GCP credentials active (e.g., gcloud auth application-default login) and Vertex AI API enabled."}
