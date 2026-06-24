"""
FintelliPro — Contact & Outreach Seeder
=========================================
Seeds realistic contacts + outreach data for all 100 NCUA CUs.
No API keys needed — uses realistic mock data based on each CU's
real NCUA profile (state, assets, charter type).

Run:
    python seed_contacts_outreach.py
"""

import sys, os, uuid, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.database import SessionLocal, init_db
from app.models import Company, Contact, AIMessage, Campaign, User

random.seed(42)

G="\033[92m"; Y="\033[93m"; C="\033[96m"; W="\033[0m"; B="\033[1m"
def ok(s):   print(f"  {G}✓{W} {s}")
def warn(s): print(f"  {Y}⚠{W}  {s}")
def hdr(s):  print(f"\n{B}{C}{s}{W}\n  {'─'*54}")

# ── Name pools ──────────────────────────────────────────────────
FIRST_NAMES = [
    "James","Michael","Robert","David","John","William","Jennifer","Linda",
    "Patricia","Barbara","Susan","Jessica","Sarah","Karen","Lisa","Nancy",
    "Daniel","Matthew","Anthony","Mark","Steven","Andrew","Paul","Kevin",
    "Ashley","Emily","Donna","Michelle","Amanda","Melissa","Rachel","Stephanie",
    "Brian","George","Joshua","Joseph","Thomas","Richard","Sandra","Carol",
    "Angela","Kathleen","Sharon","Laura","Cynthia","Dorothy","Amy","Deborah",
    "Okonkwo","Patel","Kim","Chen","Singh","Walsh","Murphy","Rivera","Torres",
]

LAST_NAMES = [
    "Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis",
    "Rodriguez","Martinez","Wilson","Anderson","Taylor","Thomas","Hernandez",
    "Moore","Jackson","Martin","Lee","Perez","Thompson","White","Harris",
    "Sanchez","Clark","Ramirez","Lewis","Robinson","Walker","Young","Allen",
    "King","Wright","Scott","Nguyen","Hill","Flores","Green","Adams","Nelson",
    "Baker","Hall","Rivera","Campbell","Mitchell","Carter","Roberts","Okafor",
    "Patel","Kim","Chen","Singh","Walsh","Murphy","Sullivan","O'Brien","Webb",
    "Gonzalez","Stewart","Morris","Rogers","Reed","Cook","Morgan","Bell","Cruz",
]

# Titles by asset tier
TITLES_ENTERPRISE = [   # >$1B
    ("Chief Digital Officer",          "c_suite"),
    ("Chief Technology Officer",        "c_suite"),
    ("Chief Information Officer",       "c_suite"),
    ("SVP of Digital Banking",          "vp"),
    ("VP of Technology & Innovation",   "vp"),
    ("VP of Digital Transformation",    "vp"),
    ("VP of Payments & Digital",        "vp"),
]
TITLES_LARGE = [         # $250M–$1B
    ("VP of Technology",                "vp"),
    ("VP of Digital Banking",           "vp"),
    ("Chief Technology Officer",        "c_suite"),
    ("Director of Information Technology","director"),
    ("VP of Operations & Technology",   "vp"),
    ("Director of Digital Transformation","director"),
]
TITLES_MID = [           # $50M–$250M
    ("IT Director",                     "director"),
    ("Director of Technology",          "director"),
    ("VP of Operations",                "vp"),
    ("Director of Digital Services",    "director"),
    ("Chief Operating Officer",         "c_suite"),
    ("VP of Member Services & IT",      "vp"),
]
TITLES_2ND = [           # secondary contact
    ("Digital Banking Manager",         "manager"),
    ("Payments Product Manager",        "manager"),
    ("Core Systems Manager",            "manager"),
    ("VP of Member Experience",         "vp"),
    ("Director of Member Services",     "director"),
    ("Senior Technology Analyst",       "staff"),
]

AREA_CODES = {
    "CA":["415","510","619","213","818","408","925"],
    "TX":["214","512","713","817","210","832"],
    "NY":["212","347","516","718","917","631"],
    "FL":["305","407","561","727","813","954"],
    "IL":["312","630","708","773","847","224"],
    "WA":["206","253","360","425","509"],
    "OH":["216","330","419","513","614","740"],
    "PA":["215","412","484","570","610","717"],
    "GA":["404","470","678","706","770","912"],
    "CO":["303","720","719","970"],
    "OR":["503","541","971"],
    "AZ":["480","520","602","623","928"],
    "MN":["218","320","507","612","651","763"],
    "MI":["248","313","517","586","616","734"],
    "VA":["240","434","540","571","703","804"],
    "NC":["336","704","828","910","919","980"],
    "IN":["219","260","317","574","765","812"],
    "WI":["262","414","608","715","920"],
    "MD":["240","301","410","443","667"],
    "MA":["339","413","508","617","781","978"],
    "HI":["808"],
    "NV":["702","725","775"],
    "UT":["385","435","801"],
    "TN":["423","615","731","865","901"],
    "MO":["314","417","573","636","816"],
}


def get_domain(name: str, website: str) -> str:
    if website and "." in website and "example" not in website:
        d = website.replace("https://","").replace("http://","").replace("www.","")
        return d.split("/")[0]
    n = name.lower()
    for s in [" federal credit union"," credit union"," fcu"," cu"," federal"," community"," financial"]:
        n = n.replace(s,"")
    n = "".join(c for c in n if c.isalnum())
    return f"{n[:20]}.org"


def pick_name():
    return random.choice(FIRST_NAMES), random.choice(LAST_NAMES)


def gen_email(first, last, domain):
    p = random.random()
    if p < 0.45: return f"{first[0].lower()}.{last.lower().replace(chr(39),'')}@{domain}"
    if p < 0.75: return f"{first.lower()}.{last.lower().replace(chr(39),'')}@{domain}"
    return f"{first.lower()}{last[0].lower()}@{domain}"


def gen_phone(state):
    if random.random() < 0.45: return None
    codes = AREA_CODES.get(state, ["800"])
    return f"+1-{random.choice(codes)}-{random.randint(200,999)}-{random.randint(1000,9999)}"


def pick_titles(assets):
    if   assets >= 1_000_000_000: pool = TITLES_ENTERPRISE
    elif assets >= 250_000_000:   pool = TITLES_LARGE
    else:                          pool = TITLES_MID

    primary = random.choice(pool)
    # Second contact probability based on size
    if assets >= 500_000_000 and random.random() < 0.80:
        return [primary, random.choice(TITLES_2ND)]
    elif assets >= 100_000_000 and random.random() < 0.55:
        return [primary, random.choice(TITLES_2ND)]
    elif random.random() < 0.30:
        return [primary, random.choice(TITLES_2ND)]
    return [primary]


def pick_status(score):
    if   score >= 90: w = {"new":0.20,"contacted":0.35,"replied":0.28,"qualified":0.17}
    elif score >= 80: w = {"new":0.30,"contacted":0.38,"replied":0.22,"qualified":0.10}
    elif score >= 70: w = {"new":0.40,"contacted":0.35,"replied":0.18,"qualified":0.07}
    else:             w = {"new":0.55,"contacted":0.30,"replied":0.12,"qualified":0.03}
    r, cum = random.random(), 0
    for status, weight in w.items():
        cum += weight
        if r <= cum: return status
    return "new"


def gen_subject(co, first_name, core):
    assets_m = (co.revenue_est or 0) // 1_000_000
    members_k = max(1, (co.regulatory_data or {}).get("total_members", 10000) // 1000)
    core_short = core.split("(")[0].strip() if core else "your core"

    templates = [
        f"Real-time payments for {co.name} — 48hr integration",
        f"{co.name} + FedNow — no core replacement needed",
        f"Quick question about {co.name}'s payment infrastructure",
        f"{first_name}, your {members_k}K members expect instant payments",
        f"API-first payments for {co.name} on {core_short}",
        f"CUNA's FedNow mandate + {co.name}",
        f"Payment modernization without replacing {core_short}",
        f"{assets_m}M in assets, still on 2-day ACH?",
    ]
    return random.choice(templates)


def gen_body(co, first_name, core):
    assets_m = (co.revenue_est or 0) // 1_000_000
    members_k = max(1, (co.regulatory_data or {}).get("total_members", 10000) // 1000)
    lts = (co.regulatory_data or {}).get("loan_to_share_ratio", 72)
    nwr = (co.regulatory_data or {}).get("net_worth_ratio", 8.5)
    core_display = core.split("(")[0].strip() if core else "your current core"
    state = co.hq_state or "your state"

    bodies = [
f"""Hi {first_name},

I was reviewing {co.name}'s NCUA profile — ${assets_m}M in assets, {members_k}K members, and running on {core_display}.

That combination tells me you're likely fielding member questions about why ACH transfers still take 2-3 days when Venmo is instant.

We've helped 40+ credit unions on {core_display} go live on FedNow in under 8 weeks — no core replacement, no disruption to existing operations. The integration sits on top of your current stack via API.

One of your peers in {state} — similar asset size — processed $2.1M in instant payments in their first month.

Worth 20 minutes to see the integration diagram for {core_display} specifically?

Best,
Alex Kumar
LeadForge | VP of Sales
alex.kumar@fintellipay.com""",

f"""Hi {first_name},

CUNA's 2025 advocacy priorities put FedNow adoption at the top of the list — which means your board is likely already asking about your timeline.

{co.name}'s {members_k}K members deserve the same instant payment experience they get from the big banks. The gap is closing fast.

We're the fastest path from {core_display} to FedNow — 48 hours of integration work, not 18 months of core migration. SOC2 Type II certified, 99.99% uptime SLA.

Your {nwr}% net worth ratio suggests a healthy balance sheet — this is exactly the right time to invest before the mandate tightens.

Open to a quick call this week?

Best,
Alex Kumar
LeadForge | VP of Sales""",

f"""Hi {first_name},

Quick question — is {co.name} currently evaluating real-time payment rails, or is that more of a 2026 initiative?

I ask because your {lts}% loan-to-share ratio tells me your members are active borrowers. Instant loan disbursement typically moves that needle 8-12 points within two quarters for CUs your size.

Either way, happy to share what we're seeing across credit unions in {state} — no pitch, just context.

Alex Kumar
LeadForge""",
    ]
    return random.choice(bodies)


def gen_linkedin(co, first_name, core):
    members_k = max(1, (co.regulatory_data or {}).get("total_members", 10000) // 1000)
    core_display = core.split("(")[0].strip() if core else "your current core"
    templates = [
        f"Hi {first_name}, saw {co.name}'s strong growth — impressive. We help credit unions on {core_display} go live on FedNow in under 8 weeks without touching the core. Would love to share how a similar CU did it. Open to connecting?",
        f"Hi {first_name}, CUNA's FedNow push has most CU boards asking the same question — what's our timeline? We've helped 40+ credit unions answer that fast. Worth connecting?",
        f"Hi {first_name}, {co.name}'s {members_k}K members are comparing their experience to Venmo every day. We close that gap for CUs on {core_display}. Could be a useful 20 mins — open to it?",
    ]
    return random.choice(templates)


def main():
    print(f"\n{B}{C}FintelliPro — Contact & Outreach Seeder{W}")

    init_db()
    db = SessionLocal()

    # Get demo user
    demo_user = db.query(User).filter_by(email="demo@leadforge.ai").first()
    if not demo_user:
        warn("Demo user not found — run seed.py first")
        demo_user_id = "a0000000-0000-0000-0000-000000000001"
    else:
        demo_user_id = demo_user.id
        ok(f"Demo user: {demo_user.email}")

    companies = db.query(Company).filter_by(industry="credit_unions") \
                  .order_by(Company.opportunity_score.desc()).all()

    if not companies:
        print("  No CUs found — run ncua_bulk_download.py first.")
        return

    print(f"  {len(companies)} credit unions found\n")

    # ── Step 1: Contacts ────────────────────────────────────────
    hdr("Step 1 — Creating contacts (1-2 per CU)")

    contact_count = 0
    company_contacts = {}  # company_id -> first contact (for messages)

    for co in companies:
        existing = db.query(Contact).filter_by(company_id=co.id).count()
        if existing > 0:
            # Grab existing for message seeding later
            c = db.query(Contact).filter_by(company_id=co.id, is_decision_maker=True).first()
            if c: company_contacts[co.id] = c
            continue

        assets = co.revenue_est or 0
        domain = get_domain(co.name, co.website or "")
        titles = pick_titles(assets)

        for i, (title, seniority) in enumerate(titles):
            first, last = pick_name()
            email = gen_email(first, last, domain)
            phone = gen_phone(co.hq_state or "")
            is_dm = seniority in ("c_suite","vp","director")
            confidence = random.randint(84, 98) if is_dm else random.randint(65, 84)

            c = Contact(
                id               = str(uuid.uuid4()),
                company_id       = co.id,
                apollo_person_id = f"seed_{co.regulatory_id}_{i}",
                first_name       = first,
                last_name        = last,
                title            = title,
                email            = email,
                email_status     = "verified" if confidence >= 85 else "probable",
                email_confidence = confidence,
                phone            = phone,
                linkedin_url     = f"linkedin.com/in/{first.lower()}-{last.lower().replace(chr(39),'')}-{random.randint(10,99)}",
                seniority_level  = seniority,
                is_decision_maker= is_dm,
            )
            db.add(c)
            if i == 0 and is_dm:
                company_contacts[co.id] = c
            contact_count += 1

        # Set outreach status based on score
        co.outreach_status = pick_status(co.opportunity_score or 50)

    db.commit()
    ok(f"Created {contact_count} contacts")

    # Reload contacts map after commit
    for co in companies:
        if co.id not in company_contacts:
            c = db.query(Contact).filter_by(company_id=co.id, is_decision_maker=True).first()
            if c: company_contacts[co.id] = c

    # ── Step 2: AI Messages for top 40 CUs ─────────────────────
    hdr("Step 2 — Creating outreach messages (top 40 CUs)")

    top_cos = [c for c in companies if (c.opportunity_score or 0) >= 70][:40]
    msg_count = 0

    for co in top_cos:
        existing = db.query(AIMessage).filter_by(company_id=co.id).count()
        if existing > 0:
            continue

        contact = company_contacts.get(co.id)
        if not contact:
            continue

        core = (co.regulatory_data or {}).get("core_processor","") or ""
        status = co.outreach_status or "new"
        is_sent = status in ("replied","qualified")
        is_approved = status in ("contacted","replied","qualified")

        # Cold email
        db.add(AIMessage(
            id           = str(uuid.uuid4()),
            company_id   = co.id,
            contact_id   = contact.id,
            owner_id     = demo_user_id,
            message_type = "email",
            subject_line = gen_subject(co, contact.first_name, core),
            body         = gen_body(co, contact.first_name, core),
            tone         = "consultative",
            model_used   = "template",
            tokens_used  = 0,
            approved     = is_approved,
            sent         = is_sent,
        ))

        # LinkedIn message for contacted/replied/qualified
        if status in ("contacted","replied","qualified"):
            db.add(AIMessage(
                id           = str(uuid.uuid4()),
                company_id   = co.id,
                contact_id   = contact.id,
                owner_id     = demo_user_id,
                message_type = "linkedin",
                subject_line = None,
                body         = gen_linkedin(co, contact.first_name, core),
                tone         = "friendly",
                model_used   = "template",
                tokens_used  = 0,
                approved     = True,
                sent         = is_sent,
            ))

        msg_count += 1

    db.commit()
    ok(f"Created messages for {msg_count} CUs")

    # ── Step 3: Campaigns ───────────────────────────────────────
    hdr("Step 3 — Creating campaigns")

    existing_camps = db.query(Campaign).count()
    if existing_camps == 0:
        camps = [
            dict(name="Credit Unions Q1 2025 — FedNow Push",       industry="credit_unions", channel="email",    status="active",    total_sent=342, total_opens=124, total_replies=28),
            dict(name="Enterprise CUs ($1B+) — Tier 1 Outreach",   industry="credit_unions", channel="email",    status="active",    total_sent=48,  total_opens=22,  total_replies=9),
            dict(name="LICU Compliance — Low Income CUs",           industry="credit_unions", channel="email",    status="active",    total_sent=87,  total_opens=34,  total_replies=11),
            dict(name="Legacy Core — Symitar & Jack Henry",         industry="credit_unions", channel="email",    status="completed", total_sent=276, total_opens=98,  total_replies=19),
            dict(name="LinkedIn — CDO & CTO Sequence",              industry="credit_unions", channel="linkedin", status="active",    total_sent=156, total_opens=71,  total_replies=22),
            dict(name="CUNA GAC 2025 Follow-Up",                    industry="credit_unions", channel="email",    status="draft",     total_sent=0,   total_opens=0,   total_replies=0),
        ]
        for cd in camps:
            db.add(Campaign(id=str(uuid.uuid4()), owner_id=demo_user_id, **cd))
        db.commit()
        ok(f"Created {len(camps)} campaigns")
    else:
        ok(f"Campaigns already exist ({existing_camps}), skipping")

    # ── Summary ─────────────────────────────────────────────────
    total_cos  = db.query(Company).count()
    total_cts  = db.query(Contact).count()
    total_msgs = db.query(AIMessage).count()
    total_cps  = db.query(Campaign).count()

    new_ct  = db.query(Company).filter_by(outreach_status="new").count()
    cont_ct = db.query(Company).filter_by(outreach_status="contacted").count()
    repl_ct = db.query(Company).filter_by(outreach_status="replied").count()
    qual_ct = db.query(Company).filter_by(outreach_status="qualified").count()

    print(f"\n{B}{C}Done!{W}\n  {'─'*54}")
    print(f"  {B}Companies:     {total_cos}{W}")
    print(f"  Contacts:      {total_cts}")
    print(f"  AI Messages:   {total_msgs}")
    print(f"  Campaigns:     {total_cps}")
    print(f"\n  Pipeline breakdown:")
    print(f"    🔵 New:        {new_ct}")
    print(f"    🟡 Contacted:  {cont_ct}")
    print(f"    🟢 Replied:    {repl_ct}")
    print(f"    ⭐ Qualified:  {qual_ct}")
    print(f"\n  {G}✅ Refresh http://localhost:3000{W}\n")
    db.close()


if __name__ == "__main__":
    main()
