"""
Standalone FastAPI router for Task 1, useful if you want to run/test triage
by itself. main.py mounts the same pipeline alongside Task 2.
"""
from fastapi import FastAPI
from pydantic import BaseModel
from src.task1_triage.pipeline import run_triage

app = FastAPI(title="Ticket Triage API")


class TriageRequest(BaseModel):
    subject: str
    body: str


@app.post("/triage")
def triage(req: TriageRequest):
    return run_triage(req.subject, req.body)
