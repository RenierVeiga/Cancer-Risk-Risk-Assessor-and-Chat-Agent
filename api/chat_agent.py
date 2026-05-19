import os
import requests
import re
import json
from datetime import datetime
from threading import Lock
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, TypedDict
from langchain_google_vertexai import ChatVertexAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from tools import GuidelineMatch, GuidelineSearchResponse, PatientRecord, get_patient_data
from settings import get_app_settings

# Create APIRouter instance for chat endpoints
router = APIRouter()

CHROMA_URL = os.environ.get("CHROMA_URL", "http://chroma:8001/search")
APP_SETTINGS = get_app_settings()
PROMPTS_PATH = os.path.join(os.path.dirname(__file__), "prompts", "CHAT_PROMPTS.md")

SESSION_STATE_LOCK = Lock()


class ChatSessionState(BaseModel):
    patient: Optional[PatientRecord] = None
    guideline_matches: List[GuidelineMatch] = Field(default_factory=list)
    last_guideline_query: Optional[str] = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


SESSION_STATE: dict[str, ChatSessionState] = {}

class ChatTurn(BaseModel):
    role: Literal["user", "model"]
    content: str

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    history: List[ChatTurn] = Field(default_factory=list)
    top_k: int = 5
    patient_id: Optional[str] = None

class Citation(BaseModel):
    source: str
    page: int
    chunk_id: str
    excerpt: str

class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    patient_id: Optional[str] = None

class ChatHistoryResponse(BaseModel):
    session_id: str
    history: List[ChatTurn] = Field(default_factory=list)

class DeleteChatResponse(BaseModel):
    session_id: str
    status: str


class GuidelineRetrievalDecision(BaseModel):
    needs_more_guidelines: bool = Field(description="Whether the current message needs new guideline retrieval.")
    refined_query: str = Field(default="", description="The best search query to use if new retrieval is needed.")
    reason: str = Field(default="", description="Brief reasoning for the retrieval decision.")


class ChatWorkflowState(TypedDict, total=False):
    session_id: str
    message: str
    history: List[ChatTurn]
    top_k: int
    patient_id: Optional[str]
    patient: Optional[PatientRecord]
    guideline_matches: List[GuidelineMatch]
    retrieval_decision: GuidelineRetrievalDecision
    answer: str
    citations: List[Citation]


def get_session_state(session_id: str) -> ChatSessionState:
    with SESSION_STATE_LOCK:
        if session_id not in SESSION_STATE:
            SESSION_STATE[session_id] = ChatSessionState()
        return SESSION_STATE[session_id]


def clear_session_state(session_id: str) -> None:
    with SESSION_STATE_LOCK:
        SESSION_STATE.pop(session_id, None)


def get_or_load_patient(session_id: str, patient_id: Optional[str]) -> Optional[PatientRecord]:
    state = get_session_state(session_id)
    if state.patient and (patient_id is None or state.patient.patient_id == patient_id):
        return state.patient

    if not patient_id:
        return state.patient

    pdata_str = get_patient_data(patient_id)
    pdata = json.loads(pdata_str)
    if "error" in pdata:
        return None

    patient = PatientRecord.model_validate(pdata)
    state.patient = patient
    state.guideline_matches = []
    state.last_guideline_query = None
    state.updated_at = datetime.utcnow()
    return patient


def build_guideline_query(patient: Optional[PatientRecord], message: str) -> str:
    if not patient:
        return message

    smoking_clause = "ever smoked" if patient.smoking_history in ["Current Smoker", "Ex-Smoker"] else "never smoked"
    return (
        f"Patient aged {patient.age}, {patient.gender.lower()}, {smoking_clause}, "
        f"presenting with: {', '.join(patient.symptoms)}. Clinical question: {message}"
    )

def _render_guideline_excerpt_summary(matches: List[GuidelineMatch], limit: int = 4) -> str:
    if not matches:
        return "No guideline excerpts currently cached."

    lines: List[str] = []
    for index, match in enumerate(matches[:limit], start=1):
        lines.append(
            f"[{index}] Page {match.page} | Chunk {match.chunk_id} | {match.source}\n"
            f"{match.document[:1000]}"
        )

    return "\n\n".join(lines)


def _load_prompt_sections() -> dict[str, str]:
    sections: dict[str, List[str]] = {}
    current_section: Optional[str] = None

    if not os.path.exists(PROMPTS_PATH):
        raise RuntimeError(f"Prompt file not found: {PROMPTS_PATH}")

    with open(PROMPTS_PATH, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.rstrip("\n")
            heading = re.match(r"^##\s+(.+?)\s*$", line)
            if heading:
                current_section = heading.group(1).strip().lower()
                sections.setdefault(current_section, [])
                continue

            if current_section:
                sections.setdefault(current_section, []).append(raw_line)

    loaded_sections = {key: "".join(value).strip() for key, value in sections.items()}

    required_sections = {
        "chat answer prompt",
        "retrieval decision prompt",
        "patient context prompt",
    }
    missing_sections = sorted(required_sections - set(loaded_sections))
    if missing_sections:
        raise RuntimeError(f"Missing prompt sections in {PROMPTS_PATH}: {', '.join(missing_sections)}")

    return loaded_sections


PROMPT_SECTIONS = _load_prompt_sections()


def _prompt_section(name: str) -> str:
    section = PROMPT_SECTIONS.get(name.lower())
    if section is None:
        raise RuntimeError(f"Missing prompt section: {name}")
    return section


def _build_retrieval_decision(session_id: str, message: str, patient: Optional[PatientRecord], cached_matches: List[GuidelineMatch]) -> GuidelineRetrievalDecision:
    app_settings = APP_SETTINGS
    llm = ChatVertexAI(
        model_name=app_settings.vertex_ai.model_name,
        project=app_settings.vertex_ai.project,
        temperature=0,
    ).with_structured_output(GuidelineRetrievalDecision)

    system_prompt = _prompt_section("retrieval decision prompt")

    patient_context = "No patient context loaded."
    if patient:
        patient_context = (
            f"Patient {patient.patient_id}: age {patient.age}, {patient.gender}, smoking history {patient.smoking_history}, "
            f"symptoms: {', '.join(patient.symptoms)}."
        )

    cached_excerpt_summary = _render_guideline_excerpt_summary(cached_matches)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Session: {session_id}\n"
                f"Patient context: {patient_context}\n"
                f"User message: {message}\n\n"
                f"Cached guideline excerpts:\n{cached_excerpt_summary}\n\n"
                f"Decide whether more guideline retrieval is needed. If it is, provide the most specific refined search query you can."
            )
        ),
    ]

    return llm.invoke(messages)


def _retrieve_guidelines(session_id: str, patient: Optional[PatientRecord], decision: GuidelineRetrievalDecision, top_k: int) -> List[GuidelineMatch]:
    state = get_session_state(session_id)
    query = decision.refined_query.strip() or build_guideline_query(patient, decision.reason or "")
    if not query:
        query = build_guideline_query(patient, "")

    try:
        response = requests.post(CHROMA_URL, json={"query": query, "k": top_k}, timeout=15)
        if response.status_code != 200:
            return state.guideline_matches

        matches = GuidelineSearchResponse.model_validate(response.json()).results
        state.guideline_matches = matches
        state.last_guideline_query = query
        state.updated_at = datetime.utcnow()
        return matches
    except Exception:
        return state.guideline_matches


def _format_guideline_context(matches: List[GuidelineMatch]) -> str:
    if not matches:
        return "No guideline chunks retrieved."

    formatted = []
    for i, match in enumerate(matches):
        formatted.append(
            f"[{i+1}] (Page: {match.page}, Chunk ID: {match.chunk_id}):\n{match.document}\n"
        )
    return "\n".join(formatted)


def _compile_chat_workflow():
    graph = StateGraph(ChatWorkflowState)

    def resolve_context(state: ChatWorkflowState) -> ChatWorkflowState:
        session_id = state["session_id"]
        patient = get_or_load_patient(session_id, state.get("patient_id"))
        current_state = get_session_state(session_id)
        state["patient"] = patient
        state["guideline_matches"] = current_state.guideline_matches
        return state

    def decide_retrieval(state: ChatWorkflowState) -> ChatWorkflowState:
        decision = _build_retrieval_decision(
            session_id=state["session_id"],
            message=state["message"],
            patient=state.get("patient"),
            cached_matches=state.get("guideline_matches", []),
        )
        state["retrieval_decision"] = decision
        return state

    def maybe_fetch_guidelines(state: ChatWorkflowState) -> ChatWorkflowState:
        decision = state.get("retrieval_decision")
        if decision and not decision.needs_more_guidelines and state.get("guideline_matches"):
            return state

        matches = _retrieve_guidelines(
            session_id=state["session_id"],
            patient=state.get("patient"),
            decision=decision or GuidelineRetrievalDecision(needs_more_guidelines=True, refined_query="", reason=""),
            top_k=state.get("top_k", 5),
        )
        state["guideline_matches"] = matches
        return state

    def answer(state: ChatWorkflowState) -> ChatWorkflowState:
        messages = []

        system_prompt = _prompt_section("chat answer prompt")

        patient = state.get("patient")
        if patient:
            patient_context = _prompt_section("patient context prompt")
            system_prompt += patient_context

        messages.append(SystemMessage(content=system_prompt))

        for turn in state.get("history", [])[-6:]:
            if turn.role == "user":
                messages.append(HumanMessage(content=turn.content))
            else:
                messages.append(AIMessage(content=turn.content))

        prompt_query = f"""Please answer the clinical query below based ONLY on the provided NICE NG12 Cancer Guidelines.

### Clinician Query:
{state['message']}

### NICE NG12 Cancer Guideline Excerpts:
{_format_guideline_context(state.get('guideline_matches', []))}
"""
        messages.append(HumanMessage(content=prompt_query))

        app_settings = APP_SETTINGS
        llm = ChatVertexAI(
            model_name=app_settings.vertex_ai.model_name,
            project=app_settings.vertex_ai.project,
            temperature=0,
        )
        model_response = llm.invoke(messages)
        answer = model_response.content.strip()

        indices = re.findall(r"\[(\d+)\]", answer)
        citations: List[Citation] = []
        seen_chunks = set()
        matches = state.get("guideline_matches", [])

        for idx_str in indices:
            idx = int(idx_str) - 1
            if 0 <= idx < len(matches):
                match = matches[idx]
                chunk_id = match.chunk_id or f"chunk_{idx}"
                if chunk_id not in seen_chunks:
                    seen_chunks.add(chunk_id)
                    citations.append(Citation(
                        source=match.source or "NG12 PDF",
                        page=match.page or 1,
                        chunk_id=chunk_id,
                        excerpt=match.document or ""
                    ))

        if not citations and matches:
            for idx, match in enumerate(matches):
                chunk_id = match.chunk_id or f"chunk_{idx}"
                citations.append(Citation(
                    source=match.source or "NG12 PDF",
                    page=match.page or 1,
                    chunk_id=chunk_id,
                    excerpt=match.document or ""
                ))

        state["answer"] = answer
        state["citations"] = citations
        return state

    graph.add_node("resolve_context", resolve_context)
    graph.add_node("decide_retrieval", decide_retrieval)
    graph.add_node("maybe_fetch_guidelines", maybe_fetch_guidelines)
    graph.add_node("answer", answer)

    graph.set_entry_point("resolve_context")
    graph.add_edge("resolve_context", "decide_retrieval")
    graph.add_conditional_edges(
        "decide_retrieval",
        lambda state: "maybe_fetch_guidelines" if state["retrieval_decision"].needs_more_guidelines else "answer",
        {
            "maybe_fetch_guidelines": "maybe_fetch_guidelines",
            "answer": "answer",
        },
    )
    graph.add_edge("maybe_fetch_guidelines", "answer")
    graph.add_edge("answer", END)

    return graph.compile()


CHAT_GRAPH = _compile_chat_workflow()

@router.post("/chat", response_model=ChatResponse)
def clinical_chat(request: ChatRequest):
    """
    Conversational clinical agent endpoint. 
    Retrieves relevant NICE guidelines, pulls conversation memory from the payload,
    and returns a clinical grounded response with accurate source citations.
    """
    if not request.session_id:
        raise HTTPException(status_code=400, detail="session_id is required.")
    if not request.message:
        raise HTTPException(status_code=400, detail="message is required.")

    # Check if message is a patient ID lookup (e.g. PT-101)
    patient_match = re.match(r"^(PT-\d+)$", request.message.strip().upper())
    if patient_match and not request.patient_id:
        pid = patient_match.group(1)
        patient = get_or_load_patient(request.session_id, pid)
        if patient:
            get_session_state(request.session_id).patient = patient
            system_prompt = "You are a professional Clinical Decision Support Chatbot specializing in the official NICE NG12 Cancer Guidelines."
            answer = f"**Patient loaded successfully:**\n\n" \
                     f"- **Name / ID**: {patient.name} ({patient.patient_id})\n" \
                     f"- **Age / Gender**: {patient.age} / {patient.gender}\n" \
                     f"- **Smoking History**: {patient.smoking_history}\n" \
                     f"- **Symptoms**: {', '.join(patient.symptoms)}\n" \
                     f"- **Symptom Duration**: {patient.symptom_duration_days} days\n\n" \
                     f"I am now ready to assist you. What questions do you have about this patient's risk profile or NICE NG12 cancer guideline referral criteria?"
            return ChatResponse(
                session_id=request.session_id,
                answer=answer,
                citations=[],
                patient_id=pid
            )
        else:
            answer = f"Patient with ID **{pid}** was not found in the database. Please verify the patient ID and try again."
            return ChatResponse(
                session_id=request.session_id,
                answer=answer,
                citations=[],
                patient_id=None
            )

    patient = get_or_load_patient(request.session_id, request.patient_id)
    if request.patient_id and not patient:
        raise HTTPException(status_code=404, detail=f"Patient with ID {request.patient_id} was not found in the database.")

    final_state = CHAT_GRAPH.invoke(
        {
            "session_id": request.session_id,
            "message": request.message,
            "history": request.history,
            "top_k": request.top_k,
            "patient_id": request.patient_id,
            "patient": patient,
            "guideline_matches": get_session_state(request.session_id).guideline_matches,
        }
    )

    resolved_patient = final_state.get("patient")
    resolved_patient_id = resolved_patient.patient_id if resolved_patient else request.patient_id

    return ChatResponse(
        session_id=request.session_id,
        answer=final_state.get("answer", ""),
        citations=final_state.get("citations", []),
        patient_id=resolved_patient_id,
    )

@router.get("/chat/{session_id}/history", response_model=ChatHistoryResponse)
def get_chat_history(session_id: str):
    """Retrieves conversation history for the session (history now resides in browser local storage)."""
    return ChatHistoryResponse(session_id=session_id, history=[])

@router.delete("/chat/{session_id}", response_model=DeleteChatResponse)
def clear_chat_history(session_id: str):
    """Clears conversation history for the session (history now resides in browser local storage)."""
    clear_session_state(session_id)
    return DeleteChatResponse(session_id=session_id, status="deleted")
