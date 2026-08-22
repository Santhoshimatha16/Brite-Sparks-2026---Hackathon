# AI Usage Disclosure

In compliance with the Brite Spark 2026 guidelines, this document outlines how AI tools were utilized during the development of this automated caseworker morning agent:

*   **Assistant/Developer**: We used Google DeepMind's Antigravity agentic coding assistant to pair-program and build the solution.
*   **Code Scaffolding**: The AI was used to scaffold the initial structures of `agent.py` and write the JSON schema mapping in `policy_rules.json`.
*   **Documentation Support**: The AI helped draft sections of `DECISIONS.md`, `README.md`, and this disclosure document.
*   **Review and Design**: The AI helped analyze Calder County DHS Authority Policy ACA-2026/1 to extract keywords and map the 12 referrals against the respective policy restrictions.
*   **LLM API Integration**: The agent is designed to dynamically call Google's Gemini API (or OpenAI's API as a fallback) to draft natural language triage and escalation notes when API keys are available in the environment.
