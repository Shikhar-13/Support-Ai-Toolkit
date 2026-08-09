"""
Entry point that mounts both pipelines behind one FastAPI app.
Run with: uvicorn main:app --reload
"""
import json
import os
from fastapi import FastAPI
from pydantic import BaseModel
from src.task1_triage.pipeline import run_triage
from src.task2_account_brief.pipeline import run_account_brief
from src.config import DATA_DIR

app = FastAPI(title="Support AI Toolkit")


def load_json(name: str):
    path = os.path.join(DATA_DIR, name)
    with open(path) as f:
        return json.load(f)


class TriageRequest(BaseModel):
    subject: str
    body: str


@app.post("/triage")
def triage(req: TriageRequest):
    return run_triage(req.subject, req.body)


@app.get("/account_brief/{account_id}")
def account_brief(account_id: str):
    accounts = load_json("accounts.json")
    tickets = load_json("tickets_sample.json")

    account = next((a for a in accounts if a["account_id"] == account_id), None)
    if account is None:
        return {"error": f"account {account_id} not found"}

    account_tickets = [t for t in tickets if t["account_id"] == account_id]
    return run_account_brief(account, account_tickets)


@app.get("/health")
def health():
    return {"status": "ok"}
