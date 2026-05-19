import os
os.environ["PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION"] = "python"

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from risk_assessor import PremiumAssessmentResult, run_assessment
from chat_agent import router as chat_router

app = FastAPI(
    title="NG12 Cancer Risk Assessor",
    description="A Clinical Decision Support Agent using Gemini 1.5 to evaluate patient records against NICE NG12 Cancer Guidelines.",
    version="1.0.0"
)

# Create static directory if it doesn't exist to prevent startup crashes
os.makedirs("static", exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    """Serves the frontend UI."""
    return FileResponse("static/index.html")

class AssessmentRequest(BaseModel):
    patient_id: str = Field(min_length=1)


class HealthResponse(BaseModel):
    status: str

@app.post("/assess", response_model=PremiumAssessmentResult)
def assess_patient(request: AssessmentRequest):
    """
    Endpoint to assess a patient's risk based on their ID.
    Retrieves data, consults guidelines, and returns an assessment.
    """
    if not request.patient_id:
        raise HTTPException(status_code=400, detail="Patient ID is required.")
        
    result = run_assessment(request.patient_id)
    
    if "error" in result:
        # Check if it's an internal error or explicitly returning an error dict
        raise HTTPException(status_code=500, detail=result)
        
    return result

# Mount the chat conversational router
app.include_router(chat_router)

# =====================================================================
# HEALTH CHECK
# =====================================================================

@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(status="healthy")
