# Calder County Automated Casework Assistant

This is an automated casework morning agent designed for the Calder County Department of Household Services. It automates the caseworker's routine morning sequence end-to-end, fetching overnight referrals, querying resident history from the Resident History API, and drafting triage notes, while strictly enforcing Authority Policy **ACA-2026/1**.

The agent features a deterministic, structured policy guardrail and a hard approval gate for supervisor reviews, ensuring no restricted action can ever proceed without explicit human sign-off.

---

## 1. Setup & Installation

### Prerequisites
*   Python 3.10+
*   Dependencies: `pip install requests`

### Step 1: Start the Resident History mock API
The agent retrieves resident information from the mock API. Run the following command in a separate terminal window to start the service:

```bash
python services/history_service.py --port 8083
```

Verify that the service is running by visiting:
[http://127.0.0.1:8083/health](http://127.0.0.1:8083/health)

---

## 2. Running the Agent

To execute the morning batch process:

```bash
python main.py
```

### How the Hard Approval Gate Works
During the run, the agent processes all 12 referrals sequentially. 
For each referral, its `requested_action` is evaluated against the `PolicyEngine`. 
If the action is marked as `REQUIRES_APPROVAL` (either because it falls strictly under Section 3, or because it is ambiguous and defaults to restricted under Section 6.1), the `ActionExecutor` physically throws an `ApprovalRequiredException`.
This structural block prevents the execution pathway from ever completing the action. The batch runner catches this exception, creates a formatted escalation document for the supervisor, and seamlessly continues processing the next referral in the queue.

---

## 3. Testing the Agent
When you run `python main.py`, verify the following expected behavior based on the required test cases:

- **Test 1:** Normal referrals (e.g., *Flag for contact attempt*, *Record change of address*) successfully result in a drafted triage note in `output/triage_RF-*.md`.
- **Test 2:** Restricted referrals (e.g., *Update payment details*, *Suspend assistance*) are instantly blocked by the policy engine and `ApprovalRequiredException`.
- **Test 3 & 5 (Continuation):** The agent does not crash on escalations or history API failures; it gracefully continues until all 12 referrals have been processed.
- **Test 4:** Ambiguous referrals (e.g., *Review award*, *Review household composition*) are aggressively treated as restricted per **Section 6.1** and escalated.

---

## 4. Output & Traceability

All run execution results and traces are stored in the `output/` directory:

*   **Triage Notes**: Permitted triage proposals are saved as `output/triage_RF-XXXX-XXXX.md`.
*   **Escalation Reports**: Refused or escalated referrals are saved as `output/escalation_RF-XXXX-XXXX.txt`, listing the policy section breached, the reason, and context for the supervisor.
*   **Execution Trace (Section 5 compliance)**:
    *   [execution_trace.json](execution_trace.json): A full machine-readable audit timeline of every step taken (referral loaded, history fetched, policy checked, action drafted/blocked, escalation created) proving exactly what the agent did and what it declined.
