import os
import json
from agent.referral_loader import load_referrals
from agent.history_client import HistoryClient
from agent.policy_engine import PolicyEngine, Decision
from agent.trace import ExecutionTrace

class ApprovalRequiredException(Exception):
    def __init__(self, action, section, reason):
        self.action = action
        self.section = section
        self.reason = reason
        super().__init__(f"Action '{action}' requires approval under {section}: {reason}")

class ActionExecutor:
    def __init__(self, policy_engine):
        self.policy_engine = policy_engine

    def execute_action(self, referral, history):
        """
        HARD APPROVAL GATE:
        Physically prevents restricted actions from proceeding without an override.
        """
        requested_action = referral["requested_action"]
        evaluation = self.policy_engine.evaluate(requested_action)
        
        if evaluation["decision"] == Decision.REQUIRES_APPROVAL:
            # Structurally unable to proceed
            raise ApprovalRequiredException(
                action=requested_action,
                section=evaluation["section"],
                reason=evaluation["reason"]
            )
        
        # If permitted, the 'action' is just drafting a triage note
        return self._draft_triage_note(referral, history)

    def _draft_triage_note(self, referral, history):
        # Generate a structured triage note
        note = f"# Triage Note for {referral['referral_id']}\n"
        note += f"**Resident Ref:** {referral['resident_ref']}\n"
        note += f"**Requested Action:** {referral['requested_action']}\n"
        note += f"**Urgency:** {referral['urgency']}\n"
        note += f"**Summary:** {referral['summary']}\n\n"
        note += "## Resident History\n"
        note += f"Status: {history['resident'].get('status', 'Unknown')}\n"
        note += f"District: {history['resident'].get('district', 'Unknown')}\n"
        return note

class EscalationManager:
    @staticmethod
    def create_escalation(referral, exception):
        escalation = f"ESCALATION\n"
        escalation += f"────────────────────────\n\n"
        escalation += f"Referral: {referral['referral_id']}\n\n"
        escalation += f"Requested action:\n{referral['requested_action']}\n\n"
        escalation += f"Policy:\n{exception.section}\n\n"
        escalation += f"Reason:\n{exception.reason}\n\n"
        escalation += f"Resident context:\nResident Ref: {referral['resident_ref']}\n\n"
        escalation += f"Agent action:\nNo restricted action was performed.\n"
        return escalation

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
        return

    for referral in referrals:
        ref_id = referral["referral_id"]
        trace.log("Referral Loaded", {"referral_id": ref_id})
        
        try:
            history = history_client.get_full_history(referral["resident_ref"])
            trace.log("Resident History Retrieved", {"referral_id": ref_id, "resident_ref": referral["resident_ref"]})
        except Exception as e:
            trace.log("History API Failure", {"referral_id": ref_id, "error": str(e)})
            continue # Handle partial failure by skipping to the next

        trace.log("Requested Action Analysed", {"referral_id": ref_id, "requested_action": referral["requested_action"]})
        
        evaluation = policy_engine.evaluate(referral["requested_action"])
        trace.log("Policy Section Checked", {"referral_id": ref_id, "decision": evaluation["decision"].value, "section": evaluation["section"]})
        
        try:
            # The execution goes through the hard gate
            triage_note = executor.execute_action(referral, history)
            
            with open(f"output/triage_{ref_id}.md", "w", encoding="utf-8") as f:
                f.write(triage_note)
                
            trace.log("Triage Note Drafted", {"referral_id": ref_id})
            
        except ApprovalRequiredException as e:
            trace.log("Action Blocked", {"referral_id": ref_id, "reason": e.reason})
            
            escalation_note = EscalationManager.create_escalation(referral, e)
            with open(f"output/escalation_{ref_id}.txt", "w", encoding="utf-8") as f:
                f.write(escalation_note)
                
            trace.log("Escalation Created", {"referral_id": ref_id})
            
        # Processing continues to the next referral (Phase 7: Continue processing)

if __name__ == "__main__":
    run_morning_batch()
    print("Morning batch run completed. Check output/ and execution_trace.json")
