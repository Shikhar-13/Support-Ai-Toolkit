"""
Thin UI over the two pipelines, meant for a non-technical TAM or support
agent to use directly -- no code required. Calls the same pipeline
functions the FastAPI endpoints call; this file has no logic of its own.

Run with: streamlit run app/streamlit_app.py
"""
import os
import sys
import json

# allow running via `streamlit run app/streamlit_app.py` from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st  
from src.config import DATA_DIR, GEMINI_API_KEY
from src.task1_triage.pipeline import run_triage
from src.task2_account_brief.pipeline import run_account_brief

st.set_page_config(page_title="Support AI Toolkit", layout="wide")
st.title("Support AI Toolkit")

if not GEMINI_API_KEY:
    st.warning(
        "GEMINI_API_KEY is not set. Add it to your .env file, then restart "
        "this app. The UI will load but pipeline calls will fail until then."
    )

tab_triage, tab_brief = st.tabs(["Ticket Triage", "Account Brief"])


def load_json(name: str):
    path = os.path.join(DATA_DIR, name)
    with open(path) as f:
        return json.load(f)


with tab_triage:
    st.subheader("Classify a ticket and draft a first response")

    col1, col2 = st.columns(2)
    with col1:
        subject = st.text_input(
            "Subject",
            placeholder="e.g. SSO configuration not working for new users",
        )
    with col2:
        st.caption(" ")

    body = st.text_area(
        "Ticket body",
        height=180,
        placeholder="Paste the full ticket text here...",
    )

    if st.button("Run triage", type="primary", disabled=not (subject and body)):
        with st.spinner("Classifying and drafting response..."):
            try:
                result = run_triage(subject, body)
            except Exception as e:
                st.error(f"Triage failed: {e}")
                result = None

        if result:
            c = result["classification"]
            urgency_color = {"P1": "red", "P2": "orange", "P3": "blue", "P4": "gray"}
            st.markdown(
                f"**Product area:** {c['product_area']}  \n"
                f"**Category:** {c['issue_category']}  \n"
                f"**Urgency:** :{urgency_color.get(c['urgency'], 'gray')}[{c['urgency']}]  \n"
                f"**Reasoning:** {c['reasoning']}"
            )

            if result["kb_match"]:
                kb = result["kb_match"]
                st.info(f"KB match: **{kb['title']}** _(category: {kb['category']}, score {kb['score']:.2f})_")
            else:
                st.caption("No close knowledge base match found.")

            st.markdown(f"**Recommended team:** {result['responder_team']}")
            st.text_area("Draft first response", value=result["draft_response"], height=150)

with tab_brief:
    st.subheader("Generate an account health brief")

    try:
        accounts = load_json("accounts.json")
        tickets_all = load_json("tickets_sample.json")
    except FileNotFoundError:
        accounts, tickets_all = [], []
        st.error("Could not find data/accounts.json or data/tickets_sample.json")

    account_ids = [a["account_id"] for a in accounts]
    selected = st.selectbox("Account", account_ids) if account_ids else None

    if selected and st.button("Generate brief", type="primary"):
        account = next(a for a in accounts if a["account_id"] == selected)
        account_tickets = [t for t in tickets_all if t["account_id"] == selected]

        with st.spinner(f"Analyzing {len(account_tickets)} tickets..."):
            try:
                brief = run_account_brief(account, account_tickets)
            except Exception as e:
                st.error(f"Brief generation failed: {e}")
                brief = None

        if brief:
            st.markdown("### Executive summary")
            st.write(brief["executive_summary"])

            st.markdown("### Open risks")
            if brief["open_risks"]:
                for r in brief["open_risks"]:
                    st.markdown(
                        f"- **[{r['risk_type']}]** {r['explanation']}  \n"
                        f"  > \"{r['quote']}\"  \n"
                        f"  _ticket {r['ticket_id']}_"
                    )
            else:
                st.caption("No flagged risks in the available tickets.")

            st.markdown("### Talking points")
            for point in brief["talking_points"]:
                st.markdown(f"- {point}")