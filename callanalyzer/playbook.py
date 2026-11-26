"""Objection-handling playbooks: the customer objections we expect, and the responses executives
should use. The AI checks each call against the playbook for its call type.

Edit or add objections here. To add a playbook for another call type, add a key to PLAYBOOKS.
"""
from __future__ import annotations

PLAYBOOKS: dict[str, list[dict]] = {
    "New Sales": [
        {"objection": "Needs time to decide", "responses": [
            "Abhi decision lene me kya help chahiye? Koi Support? After Sales / discount issue?",
            "Koi Product ke liye confusion ho toh main help karne ko ready hoon",
            "Kab follow-up karun, bataiyega?"]},
        {"objection": "Needs to discuss with family/friends/partner", "responses": [
            "Main unke saath bhi quick call arrange kar sakta hoon",
            "Demo summary bhej deta hoon taaki sab samajh saken",
            "Partner ke saath demo schedule karte hain / Dono ki agreement se hi aage badhenge"]},
        {"objection": "Didn't find benefit in demo", "responses": [
            "Batao kaunse pain points hain, main customized demo dunga",
            "Aapki problems pe focus karenge"]},
        {"objection": "Needs time to arrange money", "responses": [
            "Rates revise ho sakte hain Sir. Aaj 25% token payment kar ke rate block kar lijiye.",
            "Aapke budget ke hisaab se discuss karte hain"]},
        {"objection": "Decide after free demo period", "responses": [
            "80% clients trial mein hi decision lete hain",
            "Trial ke dauran full support milega"]},
        {"objection": "Can't afford / feels expensive", "responses": [
            "Busy se time aur errors dono bachenge",
            "Long-term mein paisa aur effort bachega"]},
        {"objection": "Software difficult to use", "responses": [
            "Tally ka course suna hoga - Busy ka suna hai? Nahi na? Bhot aasan hai chalana",
            "User-friendly design hai",
            "Personal training session arrange kar sakta hoon"]},
        {"objection": "Looking for more discount", "responses": [
            "Best offer dene ki koshish karunga (Mobile app / 3 years discount)",
            "Quality aur support compromise nahi karenge"]},
        {"objection": "Sales discussion could be better", "responses": [
            "Batao kis cheez mein clarity chahiye",
            "Main aapki madad karunga"]},
        {"objection": "Will take from local vendor / needs physical visit", "responses": [
            "Sir, whatsapp ke jamane me chithiyan kon dalta hai? Online lijiye.",
            "Sir, kal lene ke baad raat ko 10 bje support chahiye hoga to physical visit to koi nahi de payega",
            "24*7 support milega. Kabhi bhi call kar lijiye. Any problem, just call 8282828282"]},
        {"objection": "Wants to try other brands", "responses": [
            "Kisse compare kar rahe ho? Mujhse lena / mat lena, main aapki help to kar du.",
            "Jaldi decision se business grow karega"]},
        {"objection": "Decide after CA advice", "responses": [
            "25% se bhi jyada CA toh Busy hi use karte hain Sir.",
            "CA ke saath direct baat ya demo kara sakta hoon; technical doubts clear karenge"]},
        {"objection": "Not confident with after-sale service", "responses": [
            "Clients feedback share kar sakta hoon: https://busy.in/case-studies/",
            "24x7 support milega Sir. Product ki training bhi dilva dunga."]},
        {"objection": "Likes current software", "responses": [
            "Kya current software mein koi problem hai?",
            "Busy kaise solve karega, dikha sakta hoon"]},
        {"objection": "Prefers manual work", "responses": [
            "Manual time-consuming + error-prone hai",
            "Software se time bachega, kaam easy hoga"]},
    ],
}

OTHER = "Other"

# Keyword fallback when the AI describes an objection in its own words (checked in this order).
KEYWORDS: dict[str, list[tuple[tuple[str, ...], str]]] = {
    "New Sales": [
        (("discount", "offer", "cheaper", "negotiat"), "Looking for more discount"),
        ((" ca ", "ca advice", "chartered", "accountant"), "Decide after CA advice"),
        (("arrange money", "funds", "no money", "budget later", "cash"), "Needs time to arrange money"),
        (("expensive", "costly", "price", "afford", "budget"), "Can't afford / feels expensive"),
        (("partner", "family", "friend", "wife", "son", "brother", "father", "discuss with"), "Needs to discuss with family/friends/partner"),
        (("trial", "free demo period"), "Decide after free demo period"),
        (("local", "vendor", "dealer", "visit", "physical"), "Will take from local vendor / needs physical visit"),
        (("other brand", "competitor", "compare", "marg", "vyapar", "other software"), "Wants to try other brands"),
        (("after-sale", "after sale", "service", "support"), "Not confident with after-sale service"),
        (("manual", "register", "diary", "excel"), "Prefers manual work"),
        (("tally", "current software", "existing software", "happy with"), "Likes current software"),
        (("difficult", "complicated", "hard to use", "learn"), "Software difficult to use"),
        (("no benefit", "not useful", "demo not", "didn't like demo"), "Didn't find benefit in demo"),
        (("sales discussion", "salesperson", "not clear", "clarity"), "Sales discussion could be better"),
        (("time to decide", "think", "decide later", "will let you know", "later"), "Needs time to decide"),
    ],
}


def objection_names(call_type: str) -> list[str]:
    return [o["objection"] for o in PLAYBOOKS.get(call_type, [])]


def responses_for(call_type: str, objection: str) -> list[str]:
    for o in PLAYBOOKS.get(call_type, []):
        if o["objection"] == objection:
            return o["responses"]
    return []


def playbook_prompt() -> str:
    parts = []
    for ctype, items in PLAYBOOKS.items():
        parts.append(f"{ctype} objection playbook (objection -> recommended responses):")
        for i, o in enumerate(items, 1):
            parts.append(f"{i}. {o['objection']} -> " + " | ".join(o["responses"]))
    return "\n".join(parts)
