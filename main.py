import os
import json
from datetime import datetime
from agent.referral_loader import load_referrals
from agent.history_client import HistoryClient
from agent.policy_engine import PolicyEngine, Decision
from agent.trace import ExecutionTrace

class ApprovalRequiredException(Exception):
    """Raised when an action falls under Section 3.1-3.8 / 6.1 requiring supervisor approval."""
    def __init__(self, action, section, reason):
        self.action = action
        self.section = section
        self.reason = reason
        super().__init__(f"Action '{action}' requires approval under {section}: {reason}")

class SafeguardingHandOffException(Exception):
    """Raised when drafting a triage note is prohibited under Section 3.9 (minor in household)."""
    def __init__(self, section, reason, minors):
        self.section = section
        self.reason = reason
        self.minors = minors
        super().__init__(f"Safeguarding hand-off under {section}: {reason}")

def _extract_household_list(raw_household):
    if isinstance(raw_household, list):
        return raw_household
    if isinstance(raw_household, dict):
        return raw_household.get("household", [])
    return []

def _extract_events_list(raw_events):
    if isinstance(raw_events, list):
        return raw_events
    if isinstance(raw_events, dict):
        return raw_events.get("events", [])
    return []

class ActionExecutor:
    def __init__(self, policy_engine: PolicyEngine):
        self.policy_engine = policy_engine

    def execute_action(self, referral: dict, history: dict):
        """
        HARD APPROVAL & SAFEGUARDING GATE:
        1. Checks Section 3.9 Safeguarding (Child in household / unestablished composition).
        2. Evaluates requested action against Section 3.1-3.8 / 6.1.
        3. Drafts triage note ONLY if fully permitted.
        """
        household = _extract_household_list(history.get("household"))
        received_at = referral.get("received_at", "2026-03-17T00:00:00")

        # Safeguarding Check under ACA-2026/2 Section 3.9 & 5.1/5.2
        safeguarding = self.policy_engine.evaluate_safeguarding(household, reference_date=received_at)
        if safeguarding["applies"]:
            # Prohibited from producing any draft triage note (Section 2.2 / 3.9)
            raise SafeguardingHandOffException(
                section=safeguarding["section"],
                reason=safeguarding["reason"],
                minors=safeguarding["minors"]
            )

        # Policy Action Evaluation under Section 3.1-3.8 / 6.1
        requested_action = referral["requested_action"]
        evaluation = self.policy_engine.evaluate(requested_action)
        
        if evaluation["decision"] == Decision.REQUIRES_APPROVAL:
            # Structurally unable to proceed without explicit supervisor approval
            raise ApprovalRequiredException(
                action=requested_action,
                section=evaluation["section"],
                reason=evaluation["reason"]
            )
        
        # If permitted, draft the triage note proposal
        return self._draft_triage_note(referral, history)

    def _draft_triage_note(self, referral: dict, history: dict) -> str:
        res = history.get("resident", {})
        household = _extract_household_list(history.get("household"))
        events = _extract_events_list(history.get("events"))

        note = f"# Triage Note for {referral['referral_id']}\n\n"
        note += f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n"
        note += f"**Resident Ref:** {referral['resident_ref']}\n"
        note += f"**Source:** {referral.get('source', 'Unknown')}\n"
        note += f"**Requested Action:** {referral['requested_action']}\n"
        note += f"**Urgency:** {referral['urgency']}\n"
        note += f"**Summary:** {referral['summary']}\n\n"
        note += "## Resident Status & Benefit Details\n"
        note += f"- **Status:** {res.get('status', 'Unknown')}\n"
        note += f"- **Benefit Code:** {res.get('benefit_code', 'Unknown')}\n"
        note += f"- **District:** {res.get('district', 'Unknown')}\n"
        note += f"- **Monthly Award:** ${res.get('award_monthly', 0.0):.2f}\n\n"
        
        note += "## Household Composition\n"
        if household:
            for member in household:
                if isinstance(member, dict):
                    note += f"- {member.get('name')} ({member.get('relationship')}, DOB: {member.get('date_of_birth')})\n"
        else:
            note += "No household records on file.\n"
        note += "\n"

        note += "## Recent Case Events\n"
        if events:
            for ev in events:
                if isinstance(ev, dict):
                    note += f"- [{ev.get('date')}] {ev.get('type')}: {ev.get('detail')}\n"
        else:
            note += "No case events on file.\n"
        note += "\n"

        note += "## Caseworker Next Steps\n"
        note += "1. Review referral proposal and resident file.\n"
        note += "2. Adopt or amend triage recommendation.\n"
        return note

class EscalationManager:
    @staticmethod
    def create_escalation(referral: dict, history: dict, exception: ApprovalRequiredException) -> str:
        """
        Creates a formal Section 4 escalation report for a supervisor.
        Escalation says: The Department must decide whether this may happen at all.
        """
        res = history.get("resident", {}) if history else {}
        events = _extract_events_list(history.get("events")) if history else []

        escalation = "═══════════════════════════════════════════════════════════════════\n"
        escalation += " DEPARTMENT ESCALATION — SUPERVISOR APPROVAL REQUIRED (SECTION 4)\n"
        escalation += "═══════════════════════════════════════════════════════════════════\n\n"
        escalation += f"Referral ID:       {referral['referral_id']}\n"
        escalation += f"Resident Ref:      {referral['resident_ref']}\n"
        escalation += f"Received At:       {referral.get('received_at', 'Unknown')}\n"
        escalation += f"Source:            {referral.get('source', 'Unknown')}\n"
        escalation += f"Urgency:           {referral.get('urgency', 'Standard')}\n\n"
        escalation += f"Requested Action:  {referral['requested_action']}\n"
        escalation += f"Policy Section:    {exception.section}\n"
        escalation += f"Reason:            {exception.reason}\n\n"
        escalation += "Department Mandate:\n"
        escalation += "  An automated assistant cannot perform or prepare this action.\n"
        escalation += "  The Department must decide whether this action may happen at all.\n\n"
        escalation += "Resident Overview:\n"
        escalation += f"  Status: {res.get('status', 'Unknown')} | District: {res.get('district', 'Unknown')} | Award: ${res.get('award_monthly', 0.0):.2f}\n\n"
        escalation += "Case Events Context (Preserved):\n"
        if events:
            for ev in events[:5]:
                if isinstance(ev, dict):
                    escalation += f"  - [{ev.get('date')}] {ev.get('type')}: {ev.get('detail')}\n"
        else:
            escalation += "  No case events recorded.\n"
        escalation += "\nAgent Action Taken: Restricted action refused and escalated.\n"
        return escalation

class HandOffManager:
    @staticmethod
    def create_handoff(referral: dict, history: dict, exception: SafeguardingHandOffException) -> str:
        """
        Creates a Section 3.2 Hand-off to a caseworker.
        A hand-off says: This is ordinary casework that a person must do.
        Preserves all gathered history and household context so caseworker does not repeat work.
        """
        res = history.get("resident", {}) if history else {}
        household = _extract_household_list(history.get("household")) if history else []
        events = _extract_events_list(history.get("events")) if history else []

        handoff = "═══════════════════════════════════════════════════════════════════\n"
        handoff += " CASEWORKER HAND-OFF — SAFEGUARDING REVIEW (POLICY ACA-2026/2 §3.9)\n"
        handoff += "═══════════════════════════════════════════════════════════════════\n\n"
        handoff += f"Referral ID:       {referral['referral_id']}\n"
        handoff += f"Resident Ref:      {referral['resident_ref']}\n"
        handoff += f"Received At:       {referral.get('received_at', 'Unknown')}\n"
        handoff += f"Source:            {referral.get('source', 'Unknown')}\n"
        handoff += f"Urgency:           {referral.get('urgency', 'Standard')}\n\n"
        handoff += f"Referral Summary:  {referral.get('summary')}\n"
        handoff += f"Requested Action:  {referral.get('requested_action')}\n\n"
        handoff += f"Policy Rule:       {exception.section} (Safeguarding Amendment ACA-2026/2)\n"
        handoff += f"Hand-Off Reason:   {exception.reason}\n\n"
        handoff += "Nature of Hand-Off:\n"
        handoff += "  This is ordinary casework that a person must do from the outset.\n"
        handoff += "  Per Section 2.2 / 3.9, no automated draft triage note was created.\n"
        handoff += "  All pre-established information is preserved below to eliminate redundant work.\n\n"
        handoff += "───────────────────────────────────────────────────────────────────\n"
        handoff += "PRESERVED CASE CONTEXT FOR CASEWORKER\n"
        handoff += "───────────────────────────────────────────────────────────────────\n"
        handoff += f"Resident Status:   {res.get('status', 'Unknown')}\n"
        handoff += f"Benefit Code:      {res.get('benefit_code', 'Unknown')}\n"
        handoff += f"District:          {res.get('district', 'Unknown')}\n"
        handoff += f"Monthly Award:     ${res.get('award_monthly', 0.0):.2f}\n\n"
        
        handoff += "Household Composition:\n"
        if household:
            for m in household:
                if isinstance(m, dict):
                    handoff += f"  - {m.get('name')} | Relationship: {m.get('relationship')} | DOB: {m.get('date_of_birth')}\n"
        else:
            handoff += "  Household composition could not be established.\n"
        handoff += "\n"

        handoff += "Recent Case Events:\n"
        if events:
            for ev in events:
                if isinstance(ev, dict):
                    handoff += f"  - [{ev.get('date')}] {ev.get('type')}: {ev.get('detail')}\n"
        else:
            handoff += "  No case events recorded.\n"
        handoff += "\n"
        handoff += "Next Step: Assigned to Caseworker for human triage and assessment.\n"
        return handoff

def run_morning_batch():
    history_client = HistoryClient()
    policy_engine = PolicyEngine()
    executor = ActionExecutor(policy_engine)
    trace = ExecutionTrace("execution_trace.json")

    os.makedirs("output", exist_ok=True)
    
    try:
        referrals = load_referrals("referral-queue.json")
    except Exception as e:
        trace.log("Load Error", {"error": str(e)})
        print(f"Failed to load referrals: {e}")
        return

    print(f"Starting Morning Batch: {len(referrals)} referrals queued.\n")

    triage_count = 0
    escalation_count = 0
    handoff_count = 0

    for referral in referrals:
        ref_id = referral["referral_id"]
        res_ref = referral["resident_ref"]
        req_action = referral["requested_action"]
        
        trace.log("Referral Loaded", {"referral_id": ref_id, "resident_ref": res_ref})
        print(f"Processing {ref_id} ({res_ref}) - Action: '{req_action}'")
        
        # 1. Retrieve history & household composition
        history = None
        try:
            history = history_client.get_full_history(res_ref)
            household_list = _extract_household_list(history.get("household"))
            trace.log("Resident History Retrieved", {
                "referral_id": ref_id,
                "resident_ref": res_ref,
                "household_count": len(household_list)
            })
        except Exception as e:
            trace.log("History API Failure", {"referral_id": ref_id, "error": str(e)})
            print(f"  [API ERROR] Failed to fetch history for {res_ref}: {e}")
            history = {"resident": {}, "household": [], "events": []}

        # 2. Execute via Hard Approval & Safeguarding Gate
        try:
            triage_note = executor.execute_action(referral, history)
            
            # If permitted, save triage note
            with open(f"output/triage_{ref_id}.md", "w", encoding="utf-8") as f:
                f.write(triage_note)
                
            trace.log("Triage Note Drafted (Section 2.4)", {"referral_id": ref_id})
            print(f"  -> [TRIAGE PROPOSAL DRAFTED] output/triage_{ref_id}.md")
            triage_count += 1

        except SafeguardingHandOffException as she:
            # Section 3.9 Safeguarding Hand-off (ACA-2026/2)
            trace.log("Safeguarding Hand-Off (Section 3.9)", {
                "referral_id": ref_id,
                "reason": she.reason,
                "minors": she.minors
            })
            
            handoff_doc = HandOffManager.create_handoff(referral, history, she)
            with open(f"output/handoff_{ref_id}.md", "w", encoding="utf-8") as f:
                f.write(handoff_doc)
            with open(f"output/handoff_{ref_id}.txt", "w", encoding="utf-8") as f:
                f.write(handoff_doc)
                
            print(f"  -> [SAFEGUARDING HAND-OFF] output/handoff_{ref_id}.md (Child in household / Section 3.9)")
            handoff_count += 1

        except ApprovalRequiredException as are:
            # Section 4 Supervisor Escalation (ACA-2026/1 §3.1-§3.8)
            trace.log("Action Blocked & Escalated (Section 4)", {
                "referral_id": ref_id,
                "section": are.section,
                "reason": are.reason
            })
            
            escalation_doc = EscalationManager.create_escalation(referral, history, are)
            with open(f"output/escalation_{ref_id}.txt", "w", encoding="utf-8") as f:
                f.write(escalation_doc)
            with open(f"output/escalation_{ref_id}.md", "w", encoding="utf-8") as f:
                f.write(escalation_doc)
                
            print(f"  -> [SUPERVISOR ESCALATION] output/escalation_{ref_id}.txt ({are.section})")
            escalation_count += 1

    print("\n===========================================================")
    print("                    BATCH RUN SUMMARY")
    print("===========================================================")
    print(f"Total Referrals Processed:     {len(referrals)}")
    print(f"Draft Triage Proposals (S2.4): {triage_count}")
    print(f"Supervisor Escalations (S4):   {escalation_count}")
    print(f"Caseworker Hand-offs   (S3.9): {handoff_count}")
    print("Audit Trace written to:        execution_trace.json")
    print("===========================================================\n")

if __name__ == "__main__":
    run_morning_batch()
