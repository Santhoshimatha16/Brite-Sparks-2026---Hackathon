# Architectural Decisions — Calder County Caseworker Agent

This document details the architectural design choices, why they were made, and how they enforce compliance with Calder County DHS Authority Policy ACA-2026/1.

## 1. Structural Incapacity (Why the agent cannot act without a human)

The agent is **structurally incapable** of executing or preparing any restricted action (falling under Section 3 of the policy) on its own. We know this because:

*   **Bypassing the LLM for Guardrails**: The decision to flag a referral as restricted is not delegated to LLM prompts, which are prone to hallucinations, prompt injections, and compliance failures. Instead, the check is performed by **deterministic Python code** mapping the referral against structured rules in `policy_rules.json`. If a match occurs, the program triggers an immediate block or escalation.
*   **Hardcoded Approval Block**: When a restricted action is detected, the Python code execution literally halts at a blocking CLI prompt (`input()`). There is no code path that bypasses this check and registers approval.
*   **Safe Defaults (Non-Interactive Runs)**: In environments where an interactive shell is not present (e.g. automated test pipelines, daemon workers), the agent detects that `sys.stdin.isatty() == False` or that `--non-interactive` was supplied, and **automatically declines/escalates the referral**. It is impossible for a restricted action to proceed with approval unless a human explicitly types `y`/`yes` in an interactive shell.
*   **Read-Only API Integration**: The mock Resident History API does not expose any database write/mutation endpoints. The agent has no code capability to write changes back to the database, ensuring zero possibility of unauthorized state changes in Calder County's registry.

## 2. Policy as Data (Day Two Readiness)

Rather than hardcoding the policy rules directly into Python logic, we defined the policy in `policy_rules.json`.
*   **Rationale**: On "Day Two", if the department updates Policy ACA-2026/1 (e.g., adding a new restricted action or allowing a previously restricted action), we only need to update the JSON schema, not rebuild or modify the core logic of `agent.py`.
*   **Mechanism**: The `agent.py` script reads the JSON at startup and iterates over the restricted patterns to validate referrals dynamically.

## 3. Technology Stack & Fallbacks

*   **Stack**: Pure Python 3 standard library.
    *   No external libraries (like `requests` or `spacy`) are required, ensuring zero setup latency and making it trivial to run on any clean machine out-of-the-box.
*   **Dual LLM/Template Engine**:
    *   If a Gemini or OpenAI API key is supplied via environment variables (`GEMINI_API_KEY` or `OPENAI_API_KEY`), the agent calls the model to draft highly descriptive, context-aware triage/escalation notes.
    *   If no key is present, the agent automatically falls back to an offline template-based generator. This prevents the script from crashing or failing in test environments without API access.

## 4. What Was Cut for Time

*   **Advanced Semantic Keyword Parsing**: We used simple, robust string matching for keyword detection. In a production version, we would implement full semantic checking or regex-based pattern matching for the policy data to handle synonyms (e.g. "cancel" vs "terminate") more elegantly.
