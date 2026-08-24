# Calder County Automated Casework Assistant

This is an automated casework morning agent designed for the Calder County Department of Household Services. It automates the caseworker's routine morning sequence end-to-end, fetching overnight referrals, querying resident history from the Resident History API, and drafting triage notes, while strictly enforcing Authority Policy **ACA-2026/1** and Policy Amendment **ACA-2026/2**.

The agent features:
1. **Hard Approval Gate for Section 3 Restrictions:** Prohibits automated execution of restricted actions (e.g. award changes, suspensions, payment alterations, fraud assertions) and generates Section 4 supervisor escalations.
2. **Safeguarding Gate for Section 3.9 (ACA-2026/2):** Prohibits automated triage note generation for households containing minors under 18 or with unestablished composition, routing them to caseworkers via preserved-context Hand-Offs.
3. **Immutable Traceability (Section 5.1):** Generates structured execution logs in `output/execution_trace.json` and `output/execution_trace.md`.

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

### Morning Batch Processing
To execute the morning batch process:

```bash
python main.py
```

Or run the full CLI agent:

```bash
python agent.py --non-interactive
```

---

## 3. How the Gates Work

### A. Safeguarding Gate (Amendment ACA-2026/2 §3.9)
Before any triage note is drafted, the agent queries the Department's resident record and calculates the ages of all household members.
*   If a household includes a person under 18 (or if composition cannot be established per Section 5.2), the system **raises `SafeguardingHandOffException`**.
*   The agent produces a **Caseworker Hand-Off** (`output/handoff_RF-XXXX.md`). Per Section 3.3, a hand-off is distinct from an escalation: it represents ordinary casework that a person must do.
*   All gathered context (resident records, award amount, household roster, and case events) is preserved in the hand-off package so caseworkers never repeat work.

### B. Hard Approval Gate (Policy ACA-2026/1 §3.1–§3.8 & §6.1)
For all non-safeguarding referrals, the requested action is evaluated against `PolicyEngine`.
*   If the action is restricted or ambiguous (Section 6.1 default), the system **raises `ApprovalRequiredException`**.
*   The agent produces a formal **Supervisor Escalation** (`output/escalation_RF-XXXX.txt`), requiring a departmental supervisor decision.

### C. Permitted Triage Proposals (§2.4)
For standard, permitted actions involving adult-only households, the agent produces a **Triage Proposal** (`output/triage_RF-XXXX.md`) ready for caseworker adoption.

---

## 4. Output & Traceability

All run execution results and traces are stored in the `output/` directory:

*   **Triage Proposals**: Permitted triage proposals saved as `output/triage_RF-XXXX-XXXX.md`.
*   **Caseworker Hand-Offs**: Safeguarding hand-offs saved as `output/handoff_RF-XXXX-XXXX.md`.
*   **Escalation Reports**: Supervisor escalations saved as `output/escalation_RF-XXXX-XXXX.txt` and `.md`.
*   **Execution Trace (Section 5 compliance)**:
    *   `execution_trace.json`: Full machine-readable audit timeline of every step taken.
    *   `output/execution_trace.md`: Markdown summary table of all actions and state transitions.
