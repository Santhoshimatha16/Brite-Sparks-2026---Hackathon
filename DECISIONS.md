# Architectural Decisions — Calder County Caseworker Agent

This document details the architectural design choices, why they were made, and how they enforce compliance with Calder County DHS Authority Policy ACA-2026/1.

## 1. Structural Incapacity (Why the agent cannot act without a human)

The agent is **structurally incapable** of executing or preparing any restricted action (falling under Section 3 of the policy) on its own. We know this because:

*   **Hard Approval Gate in the Executor:** The code architecture strictly separates decision logic (`PolicyEngine`) from execution logic (`ActionExecutor`). Before any action is taken, the `ActionExecutor` queries the `PolicyEngine`. If the decision is `REQUIRES_APPROVAL`, the executor raises an `ApprovalRequiredException`. The execution pathway for the action is completely severed; there is no code path that allows the action to proceed.
*   **No "Suggestive" Blocks:** We do not rely on an LLM prompt telling the AI "please ask for approval". The block is hard-coded in Python at the method level.
*   **Enforcing Section 6.1:** Any action not explicitly known or understood by the `PolicyEngine` defaults to `REQUIRES_APPROVAL`. The system uses an explicit allow-list for permitted actions, aggressively escalating unclear actions.
*   **Morning Batch Safety:** Because the morning batch runs unattended, the system cannot prompt for a human decision inline. Therefore, the raised `ApprovalRequiredException` is caught by the batch runner to instantly escalate the case and continue processing the rest of the queue, adhering strictly to Section 4.1 (do not perform partial action) and Section 4.3 (continue processing others).

## 2. Policy as the Source of Truth

Rather than hard-coding checks like `if action == 'change_bank': approval` throughout the agent's logic, all rules are encapsulated in `policy_engine.py`.
*   **Rationale:** On "Day Two", if the department updates Policy ACA-2026/1, the only file that requires changes is the `PolicyEngine` configuration. The executor and main agent logic remain untouched.

## 3. Resilience and Traceability

*   **Partial Failure Handling:** The agent processes referrals sequentially in a `try/except` block. If the History API fails or an action is escalated, the error is logged, and the loop naturally continues to the next referral.
*   **Immutable Tracing:** Every state transition (referral loaded, history fetched, policy checked, action taken/blocked) is appended to an in-memory list and dumped to `execution_trace.json`. This satisfies Section 5.1, allowing a supervisor to perfectly reconstruct the agent's logic.

## 4. Frontend Excluded for Core Focus

As interface quality was not assessed and a full frontend was not strictly required, development time was focused entirely on building the un-bypassable Hard Approval Gate and comprehensive traceability mechanisms.
