# Architectural Decisions — Calder County Caseworker Agent

This document details the architectural design choices, why they were made, how they enforced compliance with Calder County DHS Authority Policy **ACA-2026/1**, and how the architecture responded to Policy Amendment **ACA-2026/2** on Day Two.

---

## 1. Structural Incapacity (Why the agent cannot act without a human)

The agent is **structurally incapable** of executing or preparing any restricted action (falling under Section 3 of the policy) on its own. We know this because:

*   **Hard Approval Gate in the Executor:** The code architecture strictly separates decision logic (`PolicyEngine`) from execution logic (`ActionExecutor`). Before any action is taken, the `ActionExecutor` queries the `PolicyEngine`. If the decision is `REQUIRES_APPROVAL`, the executor raises an `ApprovalRequiredException`. The execution pathway for the action is completely severed; there is no code path that allows the action to proceed.
*   **No "Suggestive" Blocks:** We do not rely on an LLM prompt telling the AI "please ask for approval". The block is hard-coded in Python at the method level.
*   **Enforcing Section 6.1:** Any action not explicitly known or understood by the `PolicyEngine` defaults to `REQUIRES_APPROVAL`. The system uses an explicit allow-list for permitted actions, aggressively escalating unclear actions.
*   **Morning Batch Safety:** Because the morning batch runs unattended, the system cannot prompt for a human decision inline. Therefore, the raised `ApprovalRequiredException` is caught by the batch runner to instantly escalate the case and continue processing the rest of the queue, adhering strictly to Section 4.1 (do not perform partial action) and Section 4.3 (continue processing others).

---

## 2. Policy as the Source of Truth

Rather than hard-coding checks like `if action == 'change_bank': approval` throughout the agent's logic, all rules are encapsulated in `policy_engine.py` and `policy_rules.json`.
*   **Rationale:** When policy changes or amendments are issued (as demonstrated by Amendment ACA-2026/2), core execution logic remains stable while policy rules evaluate against updated departmental mandates.

---

## 3. Resilience and Traceability

*   **Partial Failure Handling:** The agent processes referrals sequentially in a `try/except` block. If the History API fails or an action is escalated or handed off, the event is logged to the audit trace, and the loop naturally continues to the next referral.
*   **Immutable Tracing:** Every state transition (referral loaded, history fetched, safeguarding checked, policy checked, action taken/blocked/handed off) is recorded and dumped to `execution_trace.json`. This satisfies Section 5.1, allowing a supervisor to reconstruct the agent's logic after the fact.

---

## 4. Frontend Excluded for Core Focus

As interface quality was not assessed and a full frontend was not strictly required, development time was focused entirely on building the un-bypassable Hard Approval Gate and comprehensive traceability mechanisms.

---

## 5. Handling Policy Amendment ACA-2026/2 (Day Two Safeguarding Amendment)

On Day Two, Calder County DHS issued **Amendment ACA-2026/2**, inserting Section 3.9 into the Authority Policy:
> *3.9 Drafting a triage note in respect of a referral concerning a household that includes a person under the age of 18.*

The amendment mandates that triage notes for households with a child require a caseworker's judgment from the outset. Automated draft note creation is prohibited (Section 2.2 / 3.9), but pre-established information must be handed to a caseworker (Section 3.2), distinguishable from a Section 4 supervisor escalation (Section 3.3).

Here is how our architecture adapted:

### A. What We Changed

1.  **Child Safeguarding Evaluation Engine (`PolicyEngine.evaluate_safeguarding`):**
    *   Added dynamic demographic inspection of household data retrieved from the Department's Resident History API (Section 5.1).
    *   Calculates the age of every household member relative to the referral timestamp.
    *   If any member is under age 18, Section 3.9 is triggered.
    *   Enforced Section 5.2 / Section 6.1: If household composition cannot be established (missing data, API failure, or missing date of birth), Section 3.9 is strictly treated as applying.

2.  **Hard Safeguarding Gate (`ActionExecutor.execute_action`):**
    *   Added a prior safeguarding gate before action evaluation. If Section 3.9 applies, `SafeguardingHandOffException` is raised immediately, physically cutting off the execution pathway that calls `_draft_triage_note`. This ensures the assistant is structurally incapable of producing a draft note for minors (Section 2.2).

3.  **Dedicated Caseworker Hand-off Pipeline (`HandOffManager`):**
    *   Per Section 3.3, a hand-off is **not an escalation** under Section 4. An escalation asks the Department whether an action may happen at all; a hand-off routes ordinary casework to a human caseworker.
    *   `HandOffManager` generates distinct documents (`output/handoff_RF-XXXX.md` and `.txt`) with clear safeguarding branding.
    *   Per Section 3.2 and Section 4.2, all pre-established context (resident details, award amount, household composition with calculated ages, and case event history) is preserved in the hand-off package so caseworkers never have to repeat work already done.

4.  **Audit Trace Updates:**
    *   `execution_trace.json` logs explicit `Safeguarding Hand-Off (Section 3.9)` steps alongside standard triage and escalation steps for full reconstruction under Section 5.1.

### B. What We Chose Not to Change

1.  **The Hard Approval Gate Pattern:**
    *   Our decoupled design (raising typed exceptions in `ActionExecutor` to sever execution paths) accommodated `SafeguardingHandOffException` without rewriting the executor structure.
2.  **Sequential Queue Resilience:**
    *   The batch loop continues seamlessly across hand-offs, escalations, and successful triage notes without restarting or aborting (Section 4.1, 4.2, 4.3).
3.  **Core Data Schema & API Contracts:**
    *   We preserved the clean REST contract with `history_service.py` (`/residents/<ref>`), leveraging existing demographic records rather than inventing secondary queues.

### C. What We Would Have Done Differently Had We Known This Was Coming

1.  **Multi-Stage Pipeline Architecture:**
    *   On Day One, we evaluated policy strictly based on `requested_action` strings before retrieving full context.
    *   Had we known policy constraints would depend on dynamic resident demographics (such as age and household members), we would have designed a formalized multi-stage pipeline from the start:
        *   *Stage 1: Pre-Fetch Action Gate* (rejecting universally illegal actions early)
        *   *Stage 2: Context & Demographic Enrichment* (fetching history and household composition)
        *   *Stage 3: Safeguarding & Contextual Policy Gate* (evaluating household composition and conditional restrictions)
        *   *Stage 4: Dispatcher* (routing to Caseworker Hand-off, Supervisor Escalation, or Triage Proposal)
2.  **Tri-State Decision Taxonomy in Data Contracts:**
    *   Day One used binary classification (`PERMITTED` vs `REQUIRES_APPROVAL`). Introducing `HAND_OFF` as a first-class citizen in the domain model avoids overloading approval exceptions and cleanly represents human-in-the-loop triage delegation.
