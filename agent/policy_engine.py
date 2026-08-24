import enum
from datetime import datetime, date

class Decision(enum.Enum):
    PERMITTED = "PERMITTED"
    REQUIRES_APPROVAL = "REQUIRES_APPROVAL"
    HAND_OFF = "HAND_OFF"

class PolicyEngine:
    """
    Evaluates requested actions and household composition against Authority Policy ACA-2026/1
    and Policy Amendment ACA-2026/2.
    """
    def __init__(self):
        # Map known actions to their decisions and relevant policy sections under ACA-2026/1
        self._policy_map = {
            "Review award": {
                "decision": Decision.REQUIRES_APPROVAL,
                "section": "Section 3.1 / 6.1",
                "reason": "Could result in a change to entitlement/award amount. Unclear if review implies change, so treated as restricted under Section 6.1."
            },
            "Record change of address": {
                "decision": Decision.PERMITTED,
                "section": "Section 2.2 / 2.5",
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
                "reason": "Changing household composition alters entitlement. Treated as restricted under Section 6.1."
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
        Evaluates a requested action against Section 3 / Section 6.1 restrictions.
        Defaults to REQUIRES_APPROVAL per Section 6.1.
        """
        if requested_action in self._policy_map:
            return self._policy_map[requested_action]
        
        return {
            "decision": Decision.REQUIRES_APPROVAL,
            "section": "Section 6.1",
            "reason": f"Unknown action '{requested_action}'. Treated as restricted under Section 6.1."
        }

    def evaluate_safeguarding(self, household: list, reference_date=None) -> dict:
        """
        Evaluates household composition under Amendment ACA-2026/2 (Section 3.9 & Section 5.1/5.2).
        Returns a dict indicating whether Section 3.9 applies, list of minors, and reason.
        """
        if reference_date is None:
            ref_date = date(2026, 3, 17)
        elif isinstance(reference_date, str):
            try:
                ref_date = datetime.fromisoformat(reference_date.replace("Z", "")).date()
            except Exception:
                ref_date = date(2026, 3, 17)
        elif isinstance(reference_date, datetime):
            ref_date = reference_date.date()
        elif isinstance(reference_date, date):
            ref_date = reference_date
        else:
            ref_date = date(2026, 3, 17)

        # Section 5.2: Where household composition cannot be established, 3.9 is treated as applying
        if household is None or not isinstance(household, list) or len(household) == 0:
            return {
                "applies": True,
                "minors": [],
                "unestablished": True,
                "section": "Section 3.9 / 5.2",
                "reason": "Household composition could not be established; treated as restricted under Section 5.2 and Section 6.1."
            }

        minors = []
        for member in household:
            dob_str = member.get("date_of_birth")
            if not dob_str:
                return {
                    "applies": True,
                    "minors": [{"name": member.get("name", "Unknown"), "reason": "Missing DOB"}],
                    "unestablished": True,
                    "section": "Section 3.9 / 5.2",
                    "reason": f"Member {member.get('name')} has no date of birth on record; treated as applying under Section 5.2."
                }
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
                return {
                    "applies": True,
                    "minors": [{"name": member.get("name", "Unknown"), "error": str(e)}],
                    "unestablished": True,
                    "section": "Section 3.9 / 5.2",
                    "reason": f"Could not parse DOB for {member.get('name')}; treated as applying under Section 5.2."
                }

        if len(minors) > 0:
            minor_desc = ", ".join([f"{m['name']} (age {m['age']}, {m['relationship']})" for m in minors])
            return {
                "applies": True,
                "minors": minors,
                "unestablished": False,
                "section": "Section 3.9",
                "reason": f"Household includes person(s) under age 18: {minor_desc}. Safeguarding review mandates caseworker judgement from the outset."
            }

        return {
            "applies": False,
            "minors": [],
            "unestablished": False,
            "section": "N/A",
            "reason": "All household members are 18 or older."
        }
