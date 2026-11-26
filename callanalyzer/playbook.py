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
    "CLM Onboarding": [
        {"objection": "Why do you need another number?", "responses": [
            "Secure the customer's account with a recovery contact independent of the activation credentials."]},
        {"objection": "I already have a registered mobile number", "responses": [
            "This is an alternate recovery contact, independent of your activation credentials."]},
        {"objection": "I don't want to share my personal email", "responses": [
            "You can provide an email ID that you personally access and are comfortable using for recovery-related communication."]},
        {"objection": "Can I provide my dealer's number?", "responses": [
            "We recommend your own accessible alternate number so BUSY can connect directly with you when required."]},
        {"objection": "Can I provide it later?", "responses": [
            "Certainly, but completing it during onboarding helps ensure that your recovery contact is available when needed."]},
        {"objection": "Can I give my family member's details?", "responses": [
            "We recommend your own accessible alternate number so BUSY can connect directly with you when required."]},
        {"objection": "Why do you want my CA/Accountant's number?", "responses": [
            "Sir, we would like to have your CA's/Accountant's contact number so that we can keep both you and them "
            "updated about any upcoming schemes or offers relevant to them.",
            "BUSY regularly organizes webinars, and we would be happy to share the webinar links with your "
            "CA/Accountant as well, so they can participate and stay updated about BUSY's features, updates, and "
            "other relevant information."]},
        {"objection": "Busy right now / call later", "responses": [
            "Bilkul Sir, sirf 5 minute ka setup call hai taaki software bina dikkat chale.",
            "Kab call karun, aaj shaam ya kal subah? (Book the exact time as the next follow-up.)"]},
        {"objection": "Software not installed yet / will install later", "responses": [
            "Main abhi remote pe 10 minute mein install aur activate kar deta hoon, aapko kuch nahi karna.",
            "Aaj install ho jayega toh kal se billing shuru kar sakte hain."]},
        {"objection": "Doesn't know how to start / create the company", "responses": [
            "Pehli company main aapke saath abhi bana deta hoon.",
            "Training session bhi schedule kar deta hoon. Kaunsa din theek rahega?"]},
        {"objection": "Old data is in Tally/Excel - worried about moving it", "responses": [
            "Purana data laane mein hum help karenge Sir, process main abhi samjha deta hoon.",
            "Pehle masters (party, items) le aate hain, phir opening balances."]},
        {"objection": "My accountant/CA handles this - talk to them", "responses": [
            "Bilkul Sir, unka naam aur number de dijiye, main unke saath bhi setup aur training kar deta hoon.",
            "25% se zyada CA Busy hi use karte hain, unhe aasaan lagega."]},
        {"objection": "I already know about support - skip it", "responses": [
            "Sirf 30 second Sir: on-call, WhatsApp, email aur YouTube videos - chaaron details WhatsApp pe bhej deta hoon.",
            "Raat ko bhi zarurat ho toh 24x7 call kar sakte hain: 8282828282."]},
        {"objection": "Why so many questions? (business/accounting details)", "responses": [
            "Sir, aapke business ke hisaab se software set karna hai - GST, invoice format, reports sab sahi aayenge.",
            "Isse aapko sirf kaam ke features dikhayenge, time bachega."]},
        {"objection": "Wants training in person / at the office", "responses": [
            "Remote training mein aapki screen pe hi sab dikhata hoon, bilkul aamne-saamne jaisa.",
            "Videos bhi bhej deta hoon, staff baad mein dekh sakta hai."]},
        {"objection": "Activation / license key not working", "responses": [
            "Abhi check karta hoon Sir, license key aur registered email confirm kar lijiye.",
            "Na hua toh technical team ka ticket bana ke ticket number aur resolve hone ka time abhi batata hoon."]},
        {"objection": "Sales team promised something that isn't there", "responses": [
            "Sir, ye main note kar raha hoon aur sales team se confirm karke ek fixed date tak aapko bataunga."]},
        {"objection": "Hasn't received the invoice / welcome email", "responses": [
            "Abhi email confirm kar lete hain, invoice aur welcome mail dobara bhej deta hoon.",
            "WhatsApp pe bhi copy bhej deta hoon."]},
    ],
    "CLM Existing": [
        {"objection": "Complaint was ignored earlier / nobody called back", "responses": [
            "Sorry Sir, ye galti hamari taraf se hui hai. Main aapka issue personally dekh raha hoon.",
            "Aapka ticket number note kar lijiye. Ek fixed date tak resolve karke main khud call karunga.",
            "Agar us din tak solve na ho, toh seedha mujhe call kijiye."]},
        {"objection": "Stopped using the software", "responses": [
            "Kya wajah thi Sir? Kaunsa kaam atak gaya tha?",
            "Main remote session arrange kar deta hoon, 15-20 minute mein setup ho jayega.",
            "Aapka data abhi bhi safe hai, wahi se shuru kar sakte hain."]},
        {"objection": "Software has problems (sync, temporary vouchers, bill format)", "responses": [
            "Problem detail mein batayiye, abhi screen share pe dekh lete hain.",
            "Latest update mein ye issue fix hai - update main abhi karwa deta hoon.",
            "Fix hone ke baad ek test bill bana ke confirm kar lete hain."]},
        {"objection": "Wants a refund / refund was refused earlier", "responses": [
            "Sir, aapki baat main senior tak escalate kar raha hoon. Ek fixed date tak aapko answer milega.",
            "Tab tak aapki problems fix karke dikhata hoon. Agar phir bhi kaam na aaye, toh options discuss karenge.",
            "(Never promise a refund yourself.)"]},
        {"objection": "Support is slow / can't reach support", "responses": [
            "24x7 support milega Sir. Kabhi bhi call kijiye: 8282828282.",
            "Main apna direct number bhi de deta hoon, koi issue ho toh seedha mujhe bataiye."]},
        {"objection": "Staff doesn't know how to use it / operator left", "responses": [
            "Naye operator ke liye training session arrange kar deta hoon.",
            "Short help videos WhatsApp pe bhej deta hoon, staff khud bhi seekh sakta hai.",
            "Kab ka time theek rahega training ke liye?"]},
        {"objection": "Too busy for training or a call", "responses": [
            "Sirf 10 minute chahiye Sir. Aapke convenient time pe call schedule kar doon?",
            "Main summary WhatsApp pe bhej deta hoon, aap free hoke dekh lijiyega."]},
        {"objection": "Switching to / considering other software", "responses": [
            "Kya missing laga Sir Busy mein? Seedha bataiye.",
            "Wo feature Busy mein hai, main 5 minute mein dikha deta hoon.",
            "Data shift karne mein time aur risk dono hai - Busy mein aapka saara data already hai."]},
        {"objection": "Happy as it is - doesn't need anything more", "responses": [
            "Bahut accha Sir! Bas ek cheez - kya aap payment reminders / e-invoice / mobile app use kar rahe ho?",
            "Isse roz ka kaam aur time bachega. 5 minute mein dikha doon?"]},
        {"objection": "Afraid of data loss / no backup", "responses": [
            "Auto-backup set kar dete hain, roz apne aap backup hoga.",
            "Abhi screen share pe dikhata hoon backup kahan save ho raha hai."]},
        {"objection": "Business slow or closed - doesn't need it now", "responses": [
            "Samajh sakta hoon Sir. Aapka data safe rahega.",
            "Jab business phir se shuru ho, ek call kijiye, sab ready milega.",
            "Kya main kuch mahine baad ek baar check kar loon?"]},
        {"objection": "Doesn't want calls", "responses": [
            "Sorry for disturbance Sir. Bas ek baat confirm kar loon - software mein koi problem toh nahi?",
            "Aage kab call karna theek rahega, ya WhatsApp pe update bhej doon?"]},
        {"objection": "Will give a referral or review later", "responses": [
            "Koi baat nahi Sir. Bas ek naam aur number bata dijiye jinhe accounting software chahiye ho.",
            "Google review ka link WhatsApp pe bhej deta hoon, sirf 1 minute lagega."]},
        {"objection": "Will pay for the renewal / update later", "responses": [
            "Sir, renewal se updates, GST changes aur 24x7 support continue rehta hai.",
            "Main renewal team se aapke liye best option check karke batata hoon."]},
        {"objection": "Mobile app and desktop data don't match", "responses": [
            "Ye sync settings ki wajah se hota hai - abhi check karke theek kar dete hain.",
            "Fix hone ke baad dono jagah ek test entry karke match kar lete hain."]},
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
    "CLM Onboarding": [
        (("ca number", "ca's number", "accountant's number", "accountant number", "ca contact", "why ca"), "Why do you want my CA/Accountant's number?"),
        (("dealer",), "Can I provide my dealer's number?"),
        (("family", "son", "sons", "daughter", "wife", "husband", "brother", "father", "relative"), "Can I give my family member's details?"),
        (("personal email", "share email", "email"), "I don't want to share my personal email"),
        (("already registered", "registered mobile", "registered number", "already have"), "I already have a registered mobile number"),
        (("another number", "second number", "recovery number", "alternate number", "why number"), "Why do you need another number?"),
        (("provide later", "give later", "share later", "provide it later", "give it later", "share it later",
          "it later", "baad mein"), "Can I provide it later?"),
        (("accountant handles", "ca handles", "talk to my ca", "talk to accountant"), "My accountant/CA handles this - talk to them"),
        (("not installed", "install later", "installation"), "Software not installed yet / will install later"),
        (("license", "licence", "activation", "key"), "Activation / license key not working"),
        (("tally", "excel", "old data", "migration", "import"), "Old data is in Tally/Excel - worried about moving it"),
        (("promised", "promise", "sales team said"), "Sales team promised something that isn't there"),
        (("invoice", "welcome mail", "welcome email"), "Hasn't received the invoice / welcome email"),
        (("in person", "physical", "office visit", "visit"), "Wants training in person / at the office"),
        (("so many questions", "why ask", "why questions"), "Why so many questions? (business/accounting details)"),
        (("already know", "skip"), "I already know about support - skip it"),
        (("busy", "call later", "call me later", "call back"), "Busy right now / call later"),
        (("how to start", "create company", "don't know"), "Doesn't know how to start / create the company"),
    ],
    "CLM Existing": [
        (("ignored", "no one called", "nobody called", "no callback", "complaint"), "Complaint was ignored earlier / nobody called back"),
        (("refund", "money back"), "Wants a refund / refund was refused earlier"),
        (("mismatch", "don't match", "not matching", "mobile app"), "Mobile app and desktop data don't match"),
        (("sync", "temporary voucher", "bug", "error", "problem", "issue"), "Software has problems (sync, temporary vouchers, bill format)"),
        (("support", "can't reach", "slow"), "Support is slow / can't reach support"),
        (("stopped using", "not using", "don't use"), "Stopped using the software"),
        (("operator", "staff", "doesn't know how"), "Staff doesn't know how to use it / operator left"),
        (("switch", "other software", "tally", "vyapar", "marg", "competitor"), "Switching to / considering other software"),
        (("backup", "data loss", "lose data"), "Afraid of data loss / no backup"),
        (("closed", "business slow", "shut", "no business"), "Business slow or closed - doesn't need it now"),
        (("don't call", "stop calling", "no calls"), "Doesn't want calls"),
        (("referral", "review", "reference"), "Will give a referral or review later"),
        (("renewal", "renew", "pay later"), "Will pay for the renewal / update later"),
        (("happy", "no need", "doesn't need"), "Happy as it is - doesn't need anything more"),
        (("busy", "no time", "training later"), "Too busy for training or a call"),
    ],
}


def objection_names(call_type: str) -> list[str]:
    return [o["objection"] for o in PLAYBOOKS.get(call_type, [])]


def responses_for(call_type: str, objection: str) -> list[str]:
    for o in PLAYBOOKS.get(call_type, []):
        if o["objection"] == objection:
            return o["responses"]
    return []


def playbook_prompt(only: str | None = None) -> str:
    parts = []
    for ctype, items in PLAYBOOKS.items():
        if only and ctype != only:
            continue
        parts.append(f"{ctype} objection playbook (objection -> recommended responses):")
        for i, o in enumerate(items, 1):
            parts.append(f"{i}. {o['objection']} -> " + " | ".join(o["responses"]))
    return "\n".join(parts)
