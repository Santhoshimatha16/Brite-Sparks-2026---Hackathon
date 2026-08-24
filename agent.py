#!/usr/bin/env python3
"""
Calder County — Department of Household Services
Automated Casework Assistant: Morning Agent (ACA-2026/1 & ACA-2026/2 Compliant)
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, date

# Setup paths
HERE = os.path.dirname(os.path.abspath(__file__))
REFERRALS_FILE = os.path.join(HERE, "referral-queue.json")
POLICY_FILE = os.path.join(HERE, "policy_rules.json")
OUTPUT_DIR = os.path.join(HERE, "output")
HISTORY_API_URL = "http://127.0.0.1:8083"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


class AgentTrace:
    """Helper class to track execution steps for Section 5 compliance."""
    def __init__(self):
        self.trace_log = []
        self.step_counter = 0

    def add_step(self, action, details):
        self.step_counter += 1
        timestamp = datetime.now().isoformat()
        step = {
            "step_number": self.step_counter,
            "timestamp": timestamp,
            "action": action,
            "details": details
        }
        self.trace_log.append(step)
        print(f"[{timestamp}] Step {self.step_counter}: {action} - {details.get('summary', '')}")

    def save_traces(self):
        # Save structured JSON trace
        json_path = os.path.join(OUTPUT_DIR, "execution_trace.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.trace_log, f, indent=2)

        # Save readable markdown trace
        md_path = os.path.join(OUTPUT_DIR, "execution_trace.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# Agent Run Execution Trace\n")
            f.write(f"**Run Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write("| Step | Timestamp | Action | Description |\n")
            f.write("|---|---|---|---|\n")
            for step in self.trace_log:
                desc = str(step["details"].get("summary", "")).replace("\n", " ")
                f.write(f"| {step['step_number']} | {step['timestamp']} | {step['action']} | {desc} |\n")


def check_history_service():
    """Verify that the Resident History API is active."""
    try:
        with urllib.request.urlopen(f"{HISTORY_API_URL}/health", timeout=2) as r:
            if r.status == 200:
                data = json.loads(r.read().decode("utf-8"))
                if data.get("status") == "ok":
                    return True
    except Exception:
        pass
    return False


def load_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_safeguarding(household, received_at=None):
    """
    Evaluates household composition under Amendment ACA-2026/2 Section 3.9 & 5.1/5.2.
    Returns: (applies, minors_list, reason_str)
    """
    if received_at:
        try:
            ref_date = datetime.fromisoformat(str(received_at).replace("Z", "")).date()
        except Exception:
            ref_date = date(2026, 3, 17)
    else:
        ref_date = date(2026, 3, 17)

    # Section 5.2: If composition cannot be established, 3.9 applies
    if household is None or not isinstance(household, list) or len(household) == 0:
        return True, [], "Household composition could not be established; treated as restricted under Section 5.2 / 6.1"

    minors = []
    for member in household:
        dob_str = member.get("date_of_birth")
        if not dob_str:
            return True, [{"name": member.get("name", "Unknown")}], f"Member {member.get('name')} missing DOB; treated as applying under Section 5.2"
        try:
            dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
            age = ref_date.year - dob.year - ((ref_date.month, ref_date.day) < (dob.month, dob.day))
            if age < 18:
                minors.append({
                    "name": member.get("name"),
                    "relationship": member.get("relationship"),
                    "date_of_birth": dob_str,
                    "age": age
                })
        except Exception as e:
            return True, [{"name": member.get("name", "Unknown")}], f"Could not parse DOB for {member.get('name')}; treated as applying under Section 5.2"

    if len(minors) > 0:
        m_desc = ", ".join([f"{m['name']} (age {m['age']})" for m in minors])
        return True, minors, f"Household includes minor under 18: {m_desc}"

    return False, [], "All household members are 18 or older"


def evaluate_policy(referral, policy):
    """
    Structured Guardrail: Evaluate referral action against policy JSON data.
    Returns: (is_restricted, policy_section_id, policy_section_description)
    """
    req_action = referral.get("requested_action", "").strip()
    summary = referral.get("summary", "").lower()

    # Explicit allowed actions (Section 2)
    permitted_actions = {
        "Record change of address": "Section 2.2 / 2.5",
        "Flag for contact attempt": "Section 2.6",
        "Draft triage note for supervisor": "Section 2.4"
    }
    if req_action in permitted_actions:
        return False, permitted_actions[req_action], "Permitted casework action"

    for sec in policy.get("restricted", {}).get("sections", []):
        # 1. Check exact match on restricted actions
        for act in sec.get("restricted_actions", []):
            if act.lower() in req_action.lower():
                return True, sec["id"], sec["description"]

        # 2. Check keyword matches in requested action
        for kw in sec.get("keywords", []):
            if kw.lower() in req_action.lower():
                return True, sec["id"], sec["description"]

    # Fallback to Section 6.1 if unclear
    return True, "Section 6.1", "Action scope unclear; defaults to restricted under Section 6.1"



def fetch_resident_history(resident_ref, trace):
    """Retrieve full history for a resident from the history API."""
    url = f"{HISTORY_API_URL}/residents/{resident_ref}"
    trace.add_step("Fetch Resident History", {"resident_ref": resident_ref, "summary": f"Requesting history for {resident_ref} from API"})
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            if r.status == 200:
                data = json.loads(r.read().decode("utf-8"))
                trace.add_step("History API Success", {"resident_ref": resident_ref, "summary": f"Retrieved record for {resident_ref} successfully"})
                return data
    except urllib.error.HTTPError as e:
        trace.add_step("History API HTTP Error", {"resident_ref": resident_ref, "summary": f"HTTP Error {e.code} for resident {resident_ref}"})
        if e.code == 404:
            return {"error": "not_found"}
    except Exception as e:
        trace.add_step("History API Exception", {"resident_ref": resident_ref, "summary": f"Connection failed: {str(e)}"})
    return None


def draft_triage_note(referral, history, trace):
    """Draft a triage note proposal (Section 2.4)."""
    ref_id = referral["referral_id"]
    res_ref = referral["resident_ref"]
    req_action = referral["requested_action"]
    summary = referral["summary"]
    urgency = referral["urgency"]
    source = referral["source"]

    status = history.get("status", "Unknown")
    benefit_code = history.get("benefit_code", "Unknown")
    district = history.get("district", "Unknown")
    award_monthly = history.get("award_monthly", 0.0)

    household = history.get("household", [])
    household_str = ""
    for member in household:
        household_str += f"- {member['name']} ({member['relationship']}, DOB: {member['date_of_birth']})\n"

    events = history.get("events", [])
    events_str = ""
    for event in events:
        events_str += f"- [{event['date']}] {event['type']}: {event['detail']}\n"

    trace.add_step("Draft Triage Note (Proposal)", {"referral_id": ref_id, "summary": f"Drafted triage note proposal for {ref_id}"})
    note = f"""# Triage Note: {ref_id}
**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Resident Reference:** {res_ref}
**Source of Referral:** {source}
**Summary of Referral:** {summary}
**Requested Action:** {req_action}
**Urgency:** {urgency}

## Resident Summary
- **Current Status:** {status}
- **Benefit Code:** {benefit_code}
- **District:** {district}
- **Monthly Award:** ${award_monthly:.2f}

## Household Composition
{household_str if household_str else "No household records available.\n"}
## Case Events Timeline
{events_str if events_str else "No case events available.\n"}
## Situation Summary
The referral requests a '{req_action}' due to: {summary}.
Resident history shows an active benefit account in district '{district}' receiving ${award_monthly:.2f} monthly.

## Recommended Next Steps
1. Review the requested action '{req_action}' in detail.
2. Verify household and income details if necessary.
3. Update case file upon caseworker confirmation.
"""
    return note


def draft_handoff_report(referral, history, minors, reason, trace):
    """
    Draft a caseworker hand-off report under Amendment ACA-2026/2 Section 3.2.
    Preserves all gathered work so caseworker does not repeat steps.
    """
    ref_id = referral["referral_id"]
    res_ref = referral["resident_ref"]
    req_action = referral["requested_action"]
    summary = referral["summary"]
    urgency = referral["urgency"]
    source = referral["source"]

    status = history.get("status", "Unknown") if history else "Unknown"
    benefit_code = history.get("benefit_code", "Unknown") if history else "Unknown"
    district = history.get("district", "Unknown") if history else "Unknown"
    award_monthly = history.get("award_monthly", 0.0) if history else 0.0

    household = history.get("household", []) if history else []
    household_str = ""
    for member in household:
        household_str += f"- {member['name']} ({member['relationship']}, DOB: {member['date_of_birth']})\n"

    events = history.get("events", []) if history else []
    events_str = ""
    for event in events:
        events_str += f"- [{event['date']}] {event['type']}: {event['detail']}\n"

    trace.add_step("Caseworker Hand-Off Created", {
        "referral_id": ref_id,
        "summary": f"Handed off referral {ref_id} to caseworker under Section 3.9 (Safeguarding)"
    })

    note = f"""# Caseworker Hand-Off: {ref_id}
**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Resident Reference:** {res_ref}
**Source of Referral:** {source}
**Summary of Referral:** {summary}
**Requested Action:** {req_action}
**Urgency:** {urgency}

## Safeguarding Notification (Policy Amendment ACA-2026/2 §3.9)
> [!NOTE]
> **Safeguarding Determination:** This household includes a child under age 18 (or composition cannot be established).
> **Mandate:** In accordance with Authority Policy Amendment ACA-2026/2 Section 3.9, drafting a triage note for a household that includes a person under 18 requires a caseworker's judgement from the outset.
> **Nature of Hand-off (§3.3):** This hand-off is **ordinary casework that a person must do**, distinguishable from an escalation requiring a departmental supervisor decision.
> **Preserved Context (§3.2 / §4.2):** All pre-established context and case history have been compiled below so that the caseworker does not need to repeat work.

## Resident Background
- **Current Status:** {status}
- **Benefit Code:** {benefit_code}
- **District:** {district}
- **Monthly Award:** ${award_monthly:.2f}

## Household Composition (from Department Records)
{household_str if household_str else "No household records available.\n"}
## Case Events Timeline (Preserved)
{events_str if events_str else "No case events available.\n"}
## Action for Caseworker
1. Review referral and history directly.
2. Conduct human safeguarding appraisal and formulate triage decision.
"""
    return note


def draft_escalation_report(referral, history, section_id, section_desc, decision_status, decision_reason, trace):
    """Draft a Section 4 escalation report with sufficient context for a supervisor."""
    ref_id = referral["referral_id"]
    res_ref = referral["resident_ref"]
    req_action = referral["requested_action"]
    summary = referral["summary"]
    urgency = referral["urgency"]
    source = referral["source"]

    status = history.get("status", "Unknown") if history else "Unknown"
    benefit_code = history.get("benefit_code", "Unknown") if history else "Unknown"
    district = history.get("district", "Unknown") if history else "Unknown"
    award_monthly = history.get("award_monthly", 0.0) if history else 0.0

    household = history.get("household", []) if history else []
    household_str = ""
    for member in household:
        household_str += f"- {member['name']} ({member['relationship']}, DOB: {member['date_of_birth']})\n"

    events = history.get("events", []) if history else []
    events_str = ""
    for event in events:
        events_str += f"- [{event['date']}] {event['type']}: {event['detail']}\n"

    trace.add_step("Draft Escalation Report", {
        "referral_id": ref_id,
        "summary": f"Drafted Section 4 escalation report for {ref_id} ({section_id})"
    })

    note = f"""# Escalation Report: {ref_id}
**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Resident Reference:** {res_ref}
**Source of Referral:** {source}
**Summary of Referral:** {summary}
**Requested Action:** {req_action}
**Urgency:** {urgency}

## Policy Violation Details (Section 4 Escalation)
> [!IMPORTANT]
> **Action Restrained:** {req_action}
> **Policy Section:** {section_id} - {section_desc}
> **Decision:** Refused execution by automated assistant; escalated to supervisor for review.
> **Mandate (§3.3):** An escalation requires the Department to decide whether this action may happen at all.

## Supervisor Decision Status
- **Status:** {decision_status}
- **Reason:** {decision_reason}

## Case History Summary
- **Current Status:** {status}
- **Benefit Code:** {benefit_code}
- **District:** {district}
- **Monthly Award:** ${award_monthly:.2f}

## Case Events Context (Preserved)
{events_str if events_str else "No case events available.\n"}
## Supervisor Briefing
The referral requested '{req_action}', which is restricted under section {section_id} of the Authority Policy. The automated assistant blocked this action to enforce compliance. The supervisor must review the resident's case history and decide on appropriate action.
"""
    return note


def main():
    interactive = True
    if "--non-interactive" in sys.argv:
        interactive = False
    elif not sys.stdin.isatty():
        interactive = False

    print("======================================================================")
    print("Calder County Automated Casework Assistant — Morning Agent Running...")
    print(f"Policy Reference: ACA-2026/1 as amended by ACA-2026/2")
    print(f"Interactive Mode: {interactive}")
    print("======================================================================")

    # 1. Initialize trace
    trace = AgentTrace()
    trace.add_step("Agent Start", {"summary": "Casework morning sequence initiated"})

    # 2. Check mock API status
    if not check_history_service():
        print("[CRITICAL ERROR] Resident History API is not running on http://127.0.0.1:8083")
        print("Please start it first by running: python services/history_service.py --port 8083")
        trace.add_step("Agent Abort", {"summary": "Resident History API not running"})
        trace.save_traces()
        sys.exit(1)

    trace.add_step("API Check Success", {"summary": "Resident History API verified active"})

    # 3. Load configurations
    try:
        policy = load_json_file(POLICY_FILE)
        referrals = load_json_file(REFERRALS_FILE)
        trace.add_step("Configurations Loaded", {
            "summary": f"Loaded policy rules ({policy.get('policy_reference')}) and {len(referrals)} referrals"
        })
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed to load config files: {e}")
        trace.add_step("Agent Abort", {"summary": f"Config load failed: {str(e)}"})
        trace.save_traces()
        sys.exit(1)

    # 4. Process each referral
    processed_count = 0
    triage_count = 0
    escalation_count = 0
    handoff_count = 0

    for idx, ref in enumerate(referrals):
        ref_id = ref["referral_id"]
        res_ref = ref["resident_ref"]
        req_action = ref["requested_action"]
        received_at = ref.get("received_at")
        print(f"\n--- Processing Referral [{idx+1}/{len(referrals)}]: {ref_id} ({res_ref}) ---")
        trace.add_step("Process Referral Start", {"referral_id": ref_id, "summary": f"Processing referral {ref_id} for resident {res_ref}"})

        # Fetch resident history first (permitted under Section 3.1 of ACA-2026/2)
        history = fetch_resident_history(res_ref, trace)
        if not history or "error" in history:
            print(f"  [WARNING] Resident history not found or failed for {res_ref}")
            history = {"resident": {}, "household": None, "events": []}

        # Step A: Evaluate Section 3.9 Safeguarding (Child in household / unestablished composition)
        household = history.get("household", [])
        is_safeguarding, minors, safeguarding_reason = evaluate_safeguarding(household, received_at)

        if is_safeguarding:
            print(f"  [SAFEGUARDING] Section 3.9 Triggered: {safeguarding_reason}")
            handoff_content = draft_handoff_report(ref, history, minors, safeguarding_reason, trace)
            out_path = os.path.join(OUTPUT_DIR, f"handoff_{ref_id}.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(handoff_content)
            txt_path = os.path.join(OUTPUT_DIR, f"handoff_{ref_id}.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(handoff_content)
            print(f"  [HAND-OFF] Referral handed off to caseworker: output/handoff_{ref_id}.md")
            handoff_count += 1
            processed_count += 1
            continue

        # Step B: Evaluate requested action against Policy Section 3.1-3.8 / 6.1
        is_restricted, sec_id, sec_desc = evaluate_policy(ref, policy)

        if not is_restricted:
            # Fully permitted: draft triage note proposal (Section 2.4)
            note_content = draft_triage_note(ref, history, trace)
            out_path = os.path.join(OUTPUT_DIR, f"triage_{ref_id}.md")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(note_content)
            print(f"  [SUCCESS] Triage note drafted: output/triage_{ref_id}.md")
            trace.add_step("Triage Complete", {"referral_id": ref_id, "summary": f"Saved triage note to output/triage_{ref_id}.md"})
            triage_count += 1
        else:
            # Restricted Action detected! Hard approval gate
            print(f"  [WARNING] Restricted Action Detected: '{req_action}' falls under Policy Section {sec_id}")
            print(f"  Description: {sec_desc}")
            trace.add_step("Restricted Action Detected", {
                "referral_id": ref_id,
                "summary": f"Action '{req_action}' restricted under Section {sec_id} of policy"
            })

            approved = False
            decision_status = "Declined"
            decision_reason = "Escalated by Automated Casework Assistant"

            if interactive:
                # Ask the supervisor for approval
                print("\n=======================================================")
                print("                  SUPERVISOR APPROVAL REQUIRED")
                print("=======================================================")
                print(f"Referral ID: {ref_id}")
                print(f"Resident Ref: {res_ref}")
                print(f"Requested Action: {req_action}")
                print(f"Summary: {ref.get('summary')}")
                print(f"Policy Section: {sec_id} - {sec_desc}")
                print("-------------------------------------------------------")
                sys.stdout.flush()

                choice = input("Approve this action to proceed? (y/N): ").strip().lower()
                if choice == 'y':
                    approved = True
                    decision_status = "Approved"
                    decision_reason = "Approved by Supervisor via CLI"
                    print("  [APPROVED] Supervisor granted approval.")
                    trace.add_step("Supervisor Approval Granted", {
                        "referral_id": ref_id,
                        "summary": f"Supervisor approved restricted action '{req_action}' via interactive CLI"
                    })
                else:
                    print("  [DENIED] Action rejected; proceeding to escalate.")
                    trace.add_step("Supervisor Approval Denied", {
                        "referral_id": ref_id,
                        "summary": f"Supervisor denied/skipped action '{req_action}'"
                    })
            else:
                print("  [NON-INTERACTIVE] Autodeclining and escalating restricted action.")
                trace.add_step("Auto-Refusal (Non-interactive)", {
                    "referral_id": ref_id,
                    "summary": f"Auto-declined restricted action '{req_action}' in non-interactive mode"
                })

            if approved:
                note_content = draft_triage_note(ref, history, trace)
                note_content += f"\n\n---\n**SUPERVISOR DECISION:** Approved\n**Approver:** Supervisor via CLI\n**Approved At:** {datetime.now().isoformat()}\n"
                out_path = os.path.join(OUTPUT_DIR, f"triage_{ref_id}.md")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(note_content)
                triage_count += 1
            else:
                escalation_content = draft_escalation_report(
                    ref, history, sec_id, sec_desc, decision_status, decision_reason, trace
                )
                out_path = os.path.join(OUTPUT_DIR, f"escalation_{ref_id}.md")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(escalation_content)
                txt_path = os.path.join(OUTPUT_DIR, f"escalation_{ref_id}.txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    f.write(escalation_content)
                print(f"  [ESCALATED] Escalation report drafted: output/escalation_{ref_id}.md")
                trace.add_step("Escalation Complete", {"referral_id": ref_id, "summary": f"Saved escalation report to output/escalation_{ref_id}.md"})
                escalation_count += 1

        processed_count += 1

    # Save traces
    trace.add_step("Agent Finish", {
        "summary": f"Morning sequence run completed. Processed: {processed_count}, Triage Proposals: {triage_count}, Escalated: {escalation_count}, Hand-offs: {handoff_count}"
    })
    trace.save_traces()

    print("\n=======================================================")
    print("                    RUN SUMMARY")
    print("=======================================================")
    print(f"Total Referrals Processed:  {processed_count}")
    print(f"Draft Triage Proposals:     {triage_count}")
    print(f"Supervisor Escalations (S4): {escalation_count}")
    print(f"Caseworker Hand-offs (S3.9): {handoff_count}")
    print(f"Trace logs written to:      output/execution_trace.json / .md")
    print("=======================================================")


if __name__ == "__main__":
    main()
