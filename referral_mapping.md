# Referral Mapping against Authority Policy

| Referral ID | Requested Action | Authority Policy Mapping | Decision |
|---|---|---|---|
| **RF-2026-0412** | Review award | **Section 3.1 / 6.1:** A review could result in a change to entitlement or award amount. Since it's unclear if "review" implies taking the action to change it, 6.1 mandates treating it as restricted. | `REQUIRES_APPROVAL` |
| **RF-2026-0413** | Record change of address | **Permitted:** Recording an address change does not fall under Section 3 (no change to payment details or entitlement explicitly mentioned). | `PERMITTED` |
| **RF-2026-0414** | Review award | **Section 3.1 / 6.1:** Same as 0412. | `REQUIRES_APPROVAL` |
| **RF-2026-0415** | Suspend assistance pending investigation | **Section 3.2 / 3.7:** Explicitly involves suspension (3.2) and relates to suspected fraud (3.7). | `REQUIRES_APPROVAL` |
| **RF-2026-0416** | Review household composition | **Section 3.1 / 6.1:** Changing household composition typically alters entitlement. By 6.1, treated as restricted. | `REQUIRES_APPROVAL` |
| **RF-2026-0417** | Draft explanatory note | **Section 3.5 / 6.1:** An explanatory note is a communication sent to a resident (3.5). | `REQUIRES_APPROVAL` |
| **RF-2026-0418** | Review award | **Section 3.1 / 6.1:** Same as 0412. | `REQUIRES_APPROVAL` |
| **RF-2026-0419** | Record income change | **Section 3.1:** An income change directly alters the resident's entitlement/award amount. | `REQUIRES_APPROVAL` |
| **RF-2026-0420** | Flag for contact attempt | **Section 2.6:** Explicitly permitted to flag a referral for human attention. | `PERMITTED` |
| **RF-2026-0421** | Review household composition | **Section 3.1 / 6.1:** Same as 0416. | `REQUIRES_APPROVAL` |
| **RF-2026-0422** | Draft triage note for supervisor | **Section 2.4:** Explicitly permitted to draft a triage note for caseworker review. | `PERMITTED` |
| **RF-2026-0423** | Update payment details | **Section 3.4:** Explicitly restricts any change to payment details, including bank accounts. | `REQUIRES_APPROVAL` |
