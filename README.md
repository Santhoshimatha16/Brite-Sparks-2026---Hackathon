# Calder County Automated Casework Assistant

This is an automated casework morning agent designed for the Calder County Department of Household Services. It automates the caseworker's routine morning sequence end-to-end, fetching overnight referrals, querying resident history from the Resident History API, and drafting triage notes, while strictly enforcing Authority Policy **ACA-2026/1**.

The agent features a deterministic, structured policy guardrail and a hard approval gate for supervisor reviews, ensuring no restricted action can ever proceed without explicit human sign-off.

---

## 1. Setup & Installation

The project uses the **Python 3 standard library only**, meaning no external dependencies (like `pip` packages) are required to run the agent.

### Prerequisites
*   Python 3.10+ (tested with Python 3.14.0)

### Step 1: Start the Resident History mock API
The agent retrieves resident information from the mock API. Run the following command in a separate terminal window to start the service:

```bash
python services/history_service.py --port 8083
```

Verify that the service is running by visiting:
[http://127.0.0.1:8083/health](http://127.0.0.1:8083/health)

---

## 2. Running the Agent

You can run the agent in two modes depending on your environment.

### Mode A: Interactive Mode (Default)
In interactive mode, when the agent detects a restricted action (e.g. updating bank details or suspending assistance), it halts and prompts the supervisor for approval via CLI:

```bash
python agent.py
```

*When prompted, type `y` to approve the action, or press Enter/type `n` to reject and escalate.*

### Mode B: Non-Interactive Mode
In non-interactive mode, or if the terminal does not support interactive inputs, the agent will **automatically decline and escalate** all restricted actions. This is suitable for headless execution or automated test suites:

```bash
python agent.py --non-interactive
```

---

## 3. Policy as Data

All policy boundaries and restrictions are defined in [policy_rules.json](policy_rules.json). 
*   **Permitted Actions**: Logged and triaged directly.
*   **Restricted Actions (Section 3)**: Triggers the human approval gate. The mapping detects restricted actions based on exact action matches and custom keywords (e.g. `suspend`, `bank details`, `fraud`).
*   To update or add new rules (e.g., for Day Two changes), simply modify `policy_rules.json` without modifying the core program code.

---

## 4. Output & Traceability

All run execution results and traces are stored in the `output/` directory:

*   **Triage Notes**: Normal triage proposals are saved as `output/triage_RF-XXXX-XXXX.md`.
*   **Escalation Reports**: Refused or escalated referrals are saved as `output/escalation_RF-XXXX-XXXX.md`, listing the policy section breached and context for the supervisor.
*   **Execution Trace (Section 5 compliance)**:
    *   [output/execution_trace.json](output/execution_trace.json): Full machine-readable audit timeline of every step taken.
    *   [output/execution_trace.md](output/execution_trace.md): A clean, human-readable markdown table representing the run timeline.
