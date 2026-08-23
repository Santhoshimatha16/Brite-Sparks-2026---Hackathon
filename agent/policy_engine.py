import enum

class Decision(enum.Enum):
    PERMITTED = "PERMITTED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"

class PolicyEngine:
    """
    Evaluates requested actions against the authority policy.
    Any action that falls under Section 3, or is unclear (Section 6.1), requires approval.
    """
    def __init__(self):
        # Map known actions to their decisions and relevant policy sections
        self._policy_map = {
            "Review award": {
                "decision": Decision.REQUIRES_APPROVAL,
                "section": "Section 3.1 / 6.1",
                "reason": "Could result in a change to entitlement/award amount. Unclear if review implies change, so treated as restricted."
            },
            "Record change of address": {
                "decision": Decision.PERMITTED,
                "section": "N/A",
                "reason": "Recording address change does not fall under Section 3 restrictions."
            },
            "Suspend assistance pending investigation": {
                "decision": Decision.REQUIRES_APPROVAL,
                "section": "Section 3.2 / 3.7",
                "reason": "Explicitly involves suspension (3.2) and relates to suspected fraud (3.7)."
            },
            "Review household composition": {
                "decision": Decision.REQUIRES_APPROVAL,
                "section": "Section 3.1 / 6.1",
                "reason": "Changing household composition alters entitlement. Treated as restricted."
            },
            "Draft explanatory note": {
                "decision": Decision.REQUIRES_APPROVAL,
                "section": "Section 3.5 / 6.1",
                "reason": "An explanatory note is a communication sent to a resident."
            },
            "Record income change": {
                "decision": Decision.REQUIRES_APPROVAL,
                "section": "Section 3.1",
                "reason": "An income change directly alters the resident's entitlement/award amount."
            },
            "Flag for contact attempt": {
                "decision": Decision.PERMITTED,
                "section": "Section 2.6",
                "reason": "Explicitly permitted to flag a referral for human attention."
            },
            "Draft triage note for supervisor": {
                "decision": Decision.PERMITTED,
                "section": "Section 2.4",
                "reason": "Explicitly permitted to draft a triage note for caseworker review."
            },
            "Update payment details": {
                "decision": Decision.REQUIRES_APPROVAL,
                "section": "Section 3.4",
                "reason": "Explicitly restricts any change to payment details."
            }
        }

    def evaluate(self, requested_action: str) -> dict:
        """
        Returns a dict containing 'decision', 'section', and 'reason'.
        Defaults to REQUIRES_APPROVAL due to Section 6.1.
        """
        if requested_action in self._policy_map:
            return self._policy_map[requested_action]
        
        return {
            "decision": Decision.REQUIRES_APPROVAL,
            "section": "Section 6.1",
            "reason": f"Unknown action '{requested_action}'. Treated as restricted under Section 6.1."
        }
