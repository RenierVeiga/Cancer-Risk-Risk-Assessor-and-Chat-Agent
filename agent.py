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
        # Initialize the Vertex AI Gemini model
        # Note: Requires GCP authentication (e.g., gcloud auth application-default login)
        llm = ChatVertexAI(model_name="gemini-1.5-pro-preview-0409", temperature=0)
        
        # Bind the tools to the LLM
        tools = [retrieve_patient_data, retrieve_guidelines]
        llm_with_tools = llm.bind_tools(tools)
        
        # We'll build a custom simple loop for tool calling, or we can use LangGraph/AgentExecutor.
        # Given the task simplicity, an AgentExecutor or manual loop is fine. Let's use AgentExecutor.
        from langchain.agents import AgentExecutor, create_tool_calling_agent
        
        # System prompt instructions
        with open("PROMPTS.md", "r") as f:
            system_prompt = f.read()

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "Please assess patient ID: {patient_id}"),
            ("placeholder", "{agent_scratchpad}"),
        ])
        
        agent = create_tool_calling_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)
        
        # Run the agent to gather data and reason
        response = agent_executor.invoke({"patient_id": patient_id})
        output_text = response["output"]
        
        # Since we want JSON output as per requirements, we can use a secondary call to enforce the schema,
        # or ask the agent to return JSON directly. Let's use a structured output parser on the final result.
        structured_llm = llm.with_structured_output(AssessmentResult)
        
        formatting_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a formatter. Convert the following clinical assessment into the required JSON structure."),
            ("human", "{text}")
        ])
        
        chain = formatting_prompt | structured_llm
        final_result = chain.invoke({"text": output_text})
        
        return final_result.dict()
        
    except Exception as e:
        return {"error": str(e), "message": "Failed to run assessment. Ensure you have GCP credentials active (e.g., gcloud auth application-default login) and Vertex AI API enabled."}
