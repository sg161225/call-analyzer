"""Call types, their checklists, outcomes and success rules.

Edit the checklists here to change what the AI checks for each type of call.
"""
from __future__ import annotations

CALL_TYPES = {
    "New Sales": {"icon": "🆕", "about": "Enquiry or lead not yet using BUSY"},
    "Mobile App": {"icon": "📱", "about": "Selling the mobile app to existing desktop customers"},
    "Renewal": {"icon": "🔄", "about": "Yearly licence / TSS renewal"},
    "Upsell": {"icon": "⬆️", "about": "More users, a higher edition or add-ons"},
    "CLM": {"icon": "🤝", "about": "Customer Life Cycle Management: onboarding, check-ins, complaint "
                                  "follow-up and reactivating dropped customers"},
}
SALES_TYPES = ["New Sales", "Mobile App", "Renewal", "Upsell"]

CHECKLISTS: dict[str, list[str]] = {
    "New Sales": [
        "Introduced self, company and reason for the call",
        "Qualified the lead (business type, size, current billing/software, decision maker, budget, timeline)",
        "Found the customer's main pain",
        "Pitched features relevant to their business",
        "Gave pricing / plan clearly",
        "Handled objections (e.g. already using Tally/Excel, price)",
        "Booked a demo/trial or got a clear decision",
        "Agreed a dated next step",
    ],
    "Mobile App": [
        "Asked how they bill or work on the move (field staff, travel, multiple outlets)",
        "Pitched mobile billing, real-time sync and payment reminders",
        "Offered a demo or trial",
        "Handled internet / sync / cost objections",
        "Gave pricing clearly",
        "Closed with a payment link or demo date",
    ],
    "Renewal": [
        "Mentioned the renewal due date",
        "Recapped the value the customer got from BUSY",
        "Checked for and resolved open complaints",
        "Made a renewal offer (early-renewal / multi-year)",
        "Handled price objections",
        "Got a payment commitment with a date",
    ],
    "Upsell": [
        "Asked about current usage and limits (users, companies, volume)",
        "Linked the upgrade to a real pain",
        "Compared plans with a clear price difference",
        "Explained the payback / value",
        "Closed or booked a follow-up",
    ],
    "CLM": [
        "Confirmed account details (version, validity, users)",
        "Checked usage and adoption of features",
        "Asked about problems or open complaints",
        "Resolved or escalated issues with a date",
        "Explained an under-used feature that would help",
        "Checked satisfaction and risk signals",
        "Asked for a referral or review (if the customer was happy)",
        "Set the next touchpoint",
    ],
}

OUTCOMES = [
    "Payment received", "Payment promised", "Demo / trial booked", "Follow-up scheduled",
    "Issue resolved", "Issue escalated", "Undecided", "Not interested / Lost", "Unclear",
]
LOSS_REASONS = [
    "None", "Price / budget", "Using competitor / Tally / Excel", "No need / not using the software",
    "Bad past experience / unresolved issue", "Business closed or downsized",
    "Decision maker not available", "Timing / will decide later", "Other",
]
RISK_LEVELS = ["None", "Low", "Medium", "High"]

# Funnel stages (cumulative): each call counts for every stage up to the one its outcome reaches.
STAGE_OF_OUTCOME = {
    "Not interested / Lost": 1, "Unclear": 1, "Undecided": 2, "Issue escalated": 2,
    "Follow-up scheduled": 3, "Demo / trial booked": 3, "Issue resolved": 3,
    "Payment promised": 4, "Payment received": 5,
    # values used by reviews made before call types existed
    "Converted / Retained": 5,
}
FUNNEL_STAGES = ["Called", "Engaged", "Next step agreed", "Payment promised", "Payment received"]

OPEN_FOLLOWUP_OUTCOMES = {"Payment promised", "Demo / trial booked", "Follow-up scheduled",
                          "Issue escalated", "Undecided"}


def is_success(call_type: str, outcome: str, risk: str = "None") -> bool:
    """Sales calls succeed only when payment is received; CLM calls when the issue is
    resolved or the customer ends healthy (no medium/high risk and not lost)."""
    if call_type == "CLM":
        return outcome == "Issue resolved" or (
            outcome not in ("Not interested / Lost", "Issue escalated", "Unclear")
            and risk in ("None", "Low"))
    return outcome in ("Payment received", "Converted / Retained")


def is_positive(outcome: str) -> bool:
    """Broader 'went well' signal, useful while there are few paid conversions."""
    return outcome in ("Payment received", "Payment promised", "Demo / trial booked",
                       "Issue resolved", "Converted / Retained", "Follow-up scheduled")


def guess_type_from_purpose(purpose: str) -> str:
    """Classify reviews made before call types existed, from the AI's 'call purpose' text."""
    p = (purpose or "").lower()
    if "renew" in p or "tss" in p:
        return "Renewal"
    if "upsell" in p or "upgrade" in p or "add-on" in p or "additional user" in p:
        return "Upsell"
    if "mobile" in p or "app" in p:
        return "Mobile App"
    if "new sale" in p or "enquiry" in p or "inquiry" in p or "lead" in p or "prospect" in p or "demo" in p:
        return "New Sales"
    return "CLM"


def checklist_prompt() -> str:
    lines = []
    for t, items in CHECKLISTS.items():
        lines.append(f"{t} ({CALL_TYPES[t]['about']}):")
        lines += [f"  - {i}" for i in items]
    return "\n".join(lines)
