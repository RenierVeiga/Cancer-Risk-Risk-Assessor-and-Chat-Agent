# NG12 Cancer Risk Assessor Agent

This document describes the behavior and architecture of the AI Agent built into this application.

## Core Objective
The agent's primary purpose is to act as a Clinical Decision Support system. It is not meant to diagnose patients entirely on its own, but to evaluate a patient's structured data against unstructured text from the official **NICE NG12 Cancer Guidelines** and determine if they meet the criteria for:
- Urgent Referral
- Urgent Investigation
- Routine care

## Tool Usage
The agent relies on `langchain-google-vertexai` with Gemini 1.5 Pro. It has access to two specific tools:
1. `retrieve_patient_data`: Fetches the structured JSON of the patient (symptoms, age, gender) using a mocked database (`patients.json`).
2. `retrieve_guidelines`: A Retrieval-Augmented Generation (RAG) tool that queries a local ChromaDB vector store containing chunked sections of the NG12 PDF.

## Execution Flow
1. The user hits the FastAPI `/assess` endpoint with a `patient_id`.
2. The agent is initialized and instructed with `PROMPTS.md`.
3. The agent calls `retrieve_patient_data(patient_id)` to understand the patient.
4. Based on the patient's symptoms (e.g., "dysphagia"), it calls `retrieve_guidelines("dysphagia")`.
5. It cross-references the patient's age and symptoms with the returned guidelines.
6. It constructs a final assessment and enforces it into the `AssessmentResult` JSON schema, returning it to the user.
