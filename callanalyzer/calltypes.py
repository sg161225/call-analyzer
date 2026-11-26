"""Call types, their checklists, outcomes and success rules.

Edit the checklists here to change what the AI checks for each type of call.
"""
from __future__ import annotations

CALL_TYPES = {
    "New Sales": {"icon": "🆕", "about": "Enquiry or lead not yet using BUSY"},
    "Mobile App": {"icon": "📱", "about": "Selling the mobile app to existing desktop customers"},
    "Renewal": {"icon": "🔄", "about": "Yearly licence / TSS renewal"},
    "Upsell": {"icon": "⬆️", "about": "More users, a higher edition or add-ons"},
    "CLM Onboarding": {"icon": "👋", "about": "Customer Life Cycle Management, onboarding: welcome and setup call "
                                            "to a customer who has just bought a licence"},
    "CLM Existing": {"icon": "🤝", "about": "Customer Life Cycle Management, existing customers: check-ins, complaint "
                                          "follow-up and reactivating dropped customers"},
}
CLM_TYPES = ["CLM Onboarding", "CLM Existing"]
# Older reviews used a single "CLM" type; they are existing-customer calls.
LEGACY_TYPES = {"CLM": "CLM Existing"}
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
    "CLM Onboarding": [
        "Welcomed the customer and introduced self as their onboarding contact",
        "Confirmed the software is installed and activated (or helped set it up)",
        "Confirmed the registered mobile number",
        "Captured a recovery mobile number",
        "Confirmed the email for recovery",
        "Explained On-call support",
        "Explained WhatsApp support",
        "Explained Email support",
        "Shared YouTube & FAQs",
        "Asked whether the business is GST registered",
        "Asked the business type",
        "Asked the nature of business / industry",
        "Asked the existing accounting software",
        "Asked whether they have a CA",
        "Asked whether they have an accountant",
        "Offered company creation, data import or a training session",
        "Agreed the next follow-up date and time",
    ],
    "CLM Existing": [
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
    "Onboarding completed", "Issue resolved", "Issue escalated", "Undecided", "Not interested / Lost", "Unclear",
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
    "Follow-up scheduled": 3, "Demo / trial booked": 3, "Issue resolved": 3, "Onboarding completed": 3,
    "Payment promised": 4, "Payment received": 5,
    # values used by reviews made before call types existed
    "Converted / Retained": 5,
}
FUNNEL_STAGES = ["Called", "Engaged", "Next step agreed", "Payment promised", "Payment received"]

OPEN_FOLLOWUP_OUTCOMES = {"Payment promised", "Demo / trial booked", "Follow-up scheduled",
                          "Issue escalated", "Undecided"}


def canonical_type(call_type: str | None) -> str | None:
    return LEGACY_TYPES.get(call_type, call_type)


def is_success(call_type: str, outcome: str, risk: str = "None") -> bool:
    """Sales calls succeed only when payment is received. Onboarding calls when onboarding is
    completed; existing-customer CLM calls when the issue is resolved or the customer ends
    healthy (no medium/high risk and not lost)."""
    call_type = canonical_type(call_type)
    if call_type == "CLM Onboarding":
        return outcome in ("Onboarding completed", "Issue resolved") or (
            outcome == "Follow-up scheduled" and risk in ("None", "Low"))
    if call_type == "CLM Existing":
        return outcome == "Issue resolved" or (
            outcome not in ("Not interested / Lost", "Issue escalated", "Unclear")
            and risk in ("None", "Low"))
    return outcome in ("Payment received", "Converted / Retained")


def is_positive(outcome: str) -> bool:
    """Broader 'went well' signal, useful while there are few paid conversions."""
    return outcome in ("Payment received", "Payment promised", "Demo / trial booked", "Onboarding completed",
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
    if "onboard" in p or "welcome" in p or "setup" in p or "set up" in p or "activation" in p:
        return "CLM Onboarding"
    return "CLM Existing"


def checklist_prompt(only: str | None = None) -> str:
    lines = []
    for t, items in CHECKLISTS.items():
        if only and t != only:
            continue
        lines.append(f"{t} ({CALL_TYPES[t]['about']}):")
        lines += [f"  - {i}" for i in items]
    return "\n".join(lines)


# Checklist sections (for the achieve/miss dashboard) and short column labels.
# Each section lists item numbers (1-based, in CHECKLISTS order). CLM Onboarding follows the CRM form.
SECTIONS: dict[str, list[tuple[str, list[int]]]] = {
    "New Sales": [("Opening", [1]), ("Discovery", [2, 3]), ("Pitch & pricing", [4, 5]),
                  ("Objections", [6]), ("Close", [7, 8])],
    "Mobile App": [("Discovery", [1]), ("Pitch & pricing", [2, 3, 5]), ("Objections", [4]), ("Close", [6])],
    "Renewal": [("Account & value", [1, 2]), ("Issues", [3]), ("Offer & objections", [4, 5]), ("Close", [6])],
    "Upsell": [("Discovery", [1, 2]), ("Value", [3, 4]), ("Close", [5])],
    "CLM Onboarding": [("Welcome & setup", [1, 2]), ("Recovery details", [3, 4, 5]),
                       ("Support awareness", [6, 7, 8, 9]), ("Business details", [10, 11, 12]),
                       ("Accounting details", [13, 14, 15]), ("Next steps", [16, 17])],
    "CLM Existing": [("Account check", [1, 2]), ("Issues", [3, 4]), ("Value & feedback", [5, 6, 7]),
                     ("Next step", [8])],
}
SHORT_LABELS = {
    # New Sales
    "Introduced self, company and reason for the call": "Intro",
    "Qualified the lead (business type, size, current billing/software, decision maker, budget, timeline)": "Qualified lead",
    "Found the customer's main pain": "Found pain",
    "Pitched features relevant to their business": "Relevant pitch",
    "Gave pricing / plan clearly": "Pricing",
    "Handled objections (e.g. already using Tally/Excel, price)": "Objections",
    "Booked a demo/trial or got a clear decision": "Demo / decision",
    "Agreed a dated next step": "Dated next step",
    # Mobile App
    "Asked how they bill or work on the move (field staff, travel, multiple outlets)": "On-the-move need",
    "Pitched mobile billing, real-time sync and payment reminders": "App features",
    "Offered a demo or trial": "Demo / trial",
    "Handled internet / sync / cost objections": "Objections",
    "Gave pricing clearly": "Pricing",
    "Closed with a payment link or demo date": "Close",
    # Renewal
    "Mentioned the renewal due date": "Due date",
    "Recapped the value the customer got from BUSY": "Value recap",
    "Checked for and resolved open complaints": "Complaints",
    "Made a renewal offer (early-renewal / multi-year)": "Renewal offer",
    "Handled price objections": "Price objection",
    "Got a payment commitment with a date": "Payment date",
    # Upsell
    "Asked about current usage and limits (users, companies, volume)": "Usage & limits",
    "Linked the upgrade to a real pain": "Linked to pain",
    "Compared plans with a clear price difference": "Plan compare",
    "Explained the payback / value": "Payback",
    "Closed or booked a follow-up": "Close",
    # CLM Onboarding (CRM form)
    "Welcomed the customer and introduced self as their onboarding contact": "Welcome",
    "Confirmed the software is installed and activated (or helped set it up)": "Installed",
    "Confirmed the registered mobile number": "Reg. mobile",
    "Captured a recovery mobile number": "Recovery mobile",
    "Confirmed the email for recovery": "Recovery email",
    "Explained On-call support": "On-call",
    "Explained WhatsApp support": "WhatsApp",
    "Explained Email support": "Email support",
    "Shared YouTube & FAQs": "YouTube & FAQs",
    "Asked whether the business is GST registered": "GST",
    "Asked the business type": "Business type",
    "Asked the nature of business / industry": "Nature / industry",
    "Asked the existing accounting software": "Existing software",
    "Asked whether they have a CA": "CA",
    "Asked whether they have an accountant": "Accountant",
    "Offered company creation, data import or a training session": "Setup / training",
    "Agreed the next follow-up date and time": "Next follow-up",
    # CLM Existing
    "Confirmed account details (version, validity, users)": "Account details",
    "Checked usage and adoption of features": "Usage",
    "Asked about problems or open complaints": "Problems",
    "Resolved or escalated issues with a date": "Resolved / escalated",
    "Explained an under-used feature that would help": "Feature tip",
    "Checked satisfaction and risk signals": "Satisfaction",
    "Asked for a referral or review (if the customer was happy)": "Referral",
    "Set the next touchpoint": "Next touchpoint",
}


def short_label(item: str) -> str:
    return SHORT_LABELS.get(item) or (item if len(item) <= 22 else item[:20] + "…")


def sections_for(call_type: str) -> list[tuple[str, list[str]]]:
    """[(section name, [checklist items])] for a call type; one section if none is defined."""
    items = CHECKLISTS.get(call_type, [])
    secs = SECTIONS.get(call_type)
    if not secs:
        return [("Checklist", items)] if items else []
    return [(name, [items[i - 1] for i in idx if 0 < i <= len(items)]) for name, idx in secs]
