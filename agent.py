#!/usr/bin/env python3
"""
Calder County — Department of Household Services
Automated Casework Assistant: Morning Agent (ACA-2026/1 Compliant)
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

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
                desc = step["details"].get("summary", "").replace("\n", " ")
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


def evaluate_policy(referral, policy):
    """
    Structured Guardrail: Evaluate referral details against the policy JSON data.
    Returns: (is_restricted, policy_section_id, policy_section_description)
    """
    req_action = referral.get("requested_action", "").lower()
    summary = referral.get("summary", "").lower()

    # Check restricted sections
    for sec in policy.get("restricted", {}).get("sections", []):
        # 1. Check exact match on restricted actions
        for act in sec.get("restricted_actions", []):
            if act.lower() in req_action:
                return True, sec["id"], sec["description"]

        # 2. Check keyword matches
        for kw in sec.get("keywords", []):
            if kw.lower() in req_action or kw.lower() in summary:
                return True, sec["id"], sec["description"]

    return False, None, None


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


def call_llm(prompt):
    """Attempt to generate text using Gemini/OpenAI API if keys are present."""
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if gemini_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_key}"
        headers = {"Content-Type": "application/json"}
        data = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }]
        }
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"  [LLM Error] Gemini API call failed: {e}. Falling back to templates.")

    elif openai_key:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {openai_key}"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                return res_data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"  [LLM Error] OpenAI API call failed: {e}. Falling back to templates.")

    return None


def draft_triage_note(referral, history, trace):
    """Draft a triage note summarizing the situation."""
    ref_id = referral["referral_id"]
    res_ref = referral["resident_ref"]
    req_action = referral["requested_action"]
    summary = referral["summary"]
    urgency = referral["urgency"]
    source = referral["source"]

    # History details
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

    prompt = f"""You are an automated casework assistant for Calder County.
Draft a concise, professional triage note for caseworker review.
A drafted note has no effect on the case until a caseworker adopts it.

Referral Details:
- Referral ID: {ref_id}
- Resident Ref: {res_ref}
- Source: {source}
- Summary: {summary}
- Requested Action: {req_action}
- Urgency: {urgency}

Resident History:
- Current Status: {status}
- Benefit Code: {benefit_code}
- District: {district}
- Monthly Award: ${award_monthly:.2f}

Household Composition:
{household_str}

Recent Case Events:
{events_str}

Please generate a well-structured markdown note with:
1. Executive summary of the referral.
2. Resident history context.
3. Recommended next steps.
Keep it objective and professional. Do not invent any facts not in the history.
"""
    # Try calling LLM
    note = call_llm(prompt)
    if note:
        trace.add_step("Draft Triage Note (LLM)", {"referral_id": ref_id, "summary": f"Drafted triage note using LLM for {ref_id}"})
        return note

    # Fallback to template
    trace.add_step("Draft Triage Note (Template)", {"referral_id": ref_id, "summary": f"Drafted triage note using template for {ref_id}"})
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
3. Update case file upon confirmation.
"""
    return note


def draft_escalation_report(referral, history, section_id, section_desc, decision_status, decision_reason, trace):
    """Draft an escalation report with sufficient context for a supervisor."""
    ref_id = referral["referral_id"]
    res_ref = referral["resident_ref"]
    req_action = referral["requested_action"]
    summary = referral["summary"]
    urgency = referral["urgency"]
    source = referral["source"]

    # History details
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

    prompt = f"""You are an automated casework assistant for Calder County.
Generate a formal escalation report for a supervisor regarding a restricted action.

Referral Details:
- Referral ID: {ref_id}
- Resident Ref: {res_ref}
- Source: {source}
- Summary: {summary}
- Requested Action: {req_action}
- Urgency: {urgency}

Policy Violation Details:
- Action Restrained: {req_action}
- Policy Section: {section_id} - {section_desc}
- Decision: Refused execution by automated assistant; escalated to supervisor for review.

Supervisor Decision Status:
- Status: {decision_status}
- Reason: {decision_reason}

Resident History:
- Current Status: {status}
- Benefit Code: {benefit_code}
- District: {district}
- Monthly Award: ${award_monthly:.2f}

Household Composition:
{household_str}

Recent Case Events:
{events_str}

Please generate a well-structured markdown report that clearly presents:
1. Escalation justification (referencing policy section {section_id}).
2. The current status of the supervisor's decision.
3. Summary of case context for the supervisor to act without re-reading the case history.
"""
    note = call_llm(prompt)
    if note:
        trace.add_step("Draft Escalation Report (LLM)", {"referral_id": ref_id, "summary": f"Drafted escalation report using LLM for {ref_id}"})
        return note

    trace.add_step("Draft Escalation Report (Template)", {"referral_id": ref_id, "summary": f"Drafted escalation report using template for {ref_id}"})
    note = f"""# Escalation Report: {ref_id}
**Date:** {datetime.now().strftime('%Y-%m-%d')}
**Resident Reference:** {res_ref}
**Source of Referral:** {source}
**Summary of Referral:** {summary}
**Requested Action:** {req_action}
**Urgency:** {urgency}

## Policy Violation Details
> [!IMPORTANT]
> **Action Restrained:** {req_action}
> **Policy Section:** {section_id} - {section_desc}
> **Decision:** Refused execution by automated assistant; escalated to supervisor for review.

## Supervisor Decision Status
- **Status:** {decision_status}
- **Reason:** {decision_reason}

## Case History Summary
- **Current Status:** {status}
- **Benefit Code:** {benefit_code}
- **District:** {district}
- **Monthly Award:** ${award_monthly:.2f}

## Case Events Context (Recent first)
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
    permitted_count = 0
    escalated_count = 0
    approved_count = 0

    for idx, ref in enumerate(referrals):
        ref_id = ref["referral_id"]
        res_ref = ref["resident_ref"]
        req_action = ref["requested_action"]
        print(f"\n--- Processing Referral [{idx+1}/{len(referrals)}]: {ref_id} ({res_ref}) ---")
        trace.add_step("Process Referral Start", {"referral_id": ref_id, "summary": f"Processing referral {ref_id} for resident {res_ref}"})

        # Evaluate against Policy (Structured Guardrail)
        is_restricted, sec_id, sec_desc = evaluate_policy(ref, policy)

        history = None
        if not is_restricted:
            # Permitted to proceed: fetch history and draft triage note
            history = fetch_resident_history(res_ref, trace)
            if history and "error" not in history:
                note_content = draft_triage_note(ref, history, trace)
                out_path = os.path.join(OUTPUT_DIR, f"triage_{ref_id}.md")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(note_content)
                print(f"  [SUCCESS] Triage note drafted: output/triage_{ref_id}.md")
                trace.add_step("Triage Complete", {"referral_id": ref_id, "summary": f"Saved triage note to output/triage_{ref_id}.md"})
                permitted_count += 1
            else:
                print(f"  [ERROR] Resident history not found or failed for {res_ref}")
                trace.add_step("Process Referral Fail", {"referral_id": ref_id, "summary": f"Resident history fetch failed for {res_ref}"})
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
                # Ask the supervisor for approval (Hard approval gate)
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

                # Get human decision
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
                # Non-interactive mode automatically declines and escalates
                print("  [NON-INTERACTIVE] Autodeclining and escalating restricted action.")
                trace.add_step("Auto-Refusal (Non-interactive)", {
                    "referral_id": ref_id,
                    "summary": f"Auto-declined restricted action '{req_action}' in non-interactive mode"
                })

            # Fetch resident history for escalation report context
            history = fetch_resident_history(res_ref, trace)

            if approved:
                # Draft note noting approval
                note_content = draft_triage_note(ref, history, trace)
                # Append approval stamp
                note_content += f"\n\n---\n**SUPERVISOR DECISION:** Approved\n**Approver:** Supervisor via CLI\n**Approved At:** {datetime.now().isoformat()}\n"
                out_path = os.path.join(OUTPUT_DIR, f"triage_{ref_id}.md")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(note_content)
                approved_count += 1
                permitted_count += 1
            else:
                # Draft formal escalation report
                escalation_content = draft_escalation_report(
                    ref, history, sec_id, sec_desc, decision_status, decision_reason, trace
                )
                out_path = os.path.join(OUTPUT_DIR, f"escalation_{ref_id}.md")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(escalation_content)
                print(f"  [ESCALATED] Escalation report drafted: output/escalation_{ref_id}.md")
                trace.add_step("Escalation Complete", {"referral_id": ref_id, "summary": f"Saved escalation report to output/escalation_{ref_id}.md"})
                escalated_count += 1

        processed_count += 1

    # Save traces
    trace.add_step("Agent Finish", {
        "summary": f"Morning sequence run completed. Processed: {processed_count}, Permitted/Approved: {permitted_count}, Escalated: {escalated_count}"
    })
    trace.save_traces()

    print("\n=======================================================")
    print("                    RUN SUMMARY")
    print("=======================================================")
    print(f"Total Referrals Processed: {processed_count}")
    print(f"Permitted without Gate:    {permitted_count - approved_count}")
    print(f"Restricted and Approved:   {approved_count}")
    print(f"Restricted and Escalated:  {escalated_count}")
    print(f"Trace logs written to:     output/execution_trace.json / .md")
    print("=======================================================")


if __name__ == "__main__":
    main()
