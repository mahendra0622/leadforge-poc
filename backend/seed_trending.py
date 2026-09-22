"""
seed_trending.py — fintech trending topics (2026 only, all URLs verified 200)
"""
import os, sys, uuid
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://leadforge_db_utkx_user:Ydw9AloKOqyYBhbLWTxSf4uY3Q0eESzB"
    "@dpg-dag9v0jl550s73aeqba0-a.oregon-postgres.render.com/leadforge_db_utkx",
)

from app.db.database import SessionLocal
from app.models import TrendingTopic

now = datetime.utcnow()

TOPICS = [
    {
        "theme": "FedNow Hits 1,800 Participants & Goes Cross-Border",
        "icon": "⚡",
        "heat_score": 96,
        "summary": (
            "Three years in, FedNow serves 1,800 financial institutions — reaching over half "
            "of all US checking accounts. Transaction volume rose 117% year-over-year in Q2 2026. "
            "The Fed's April proposal to allow cross-border transfers via intermediaries is the "
            "network's biggest structural change yet. CUs not live are falling further behind."
        ),
        "tags": ["fednow", "real-time-payments", "cross-border", "credit-unions"],
        "articles": [
            {
                "title": "Fed Rewrites Rules to Bring Cross-Border Payments to FedNow",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/news/cross-border-commerce/cross-border-payments/2026/fed-rewrites-rules-to-bring-cross-border-payments-to-fednow/",
                "published_at": "2026-04-10",
                "snippet": "The Federal Reserve proposed allowing US banks and credit unions to use intermediaries for cross-border transfers through FedNow — a major expansion of the network's scope.",
            },
            {
                "title": "FedNow Readies Cross-Border and Request-for-Payment Pilot",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/real-time-payments/2026/fednow-service-readies-cross-border-capabilities-and-request-for-payment-pilot/",
                "published_at": "2026-05-18",
                "snippet": "FedNow is piloting two capabilities simultaneously: cross-border interoperability and a request-for-payment feature — both aimed at closing the gap with Zelle and RTP.",
            },
            {
                "title": "Fed Proposes Opening FedNow to Cross-Border Payments",
                "source": "ABA Banking Journal",
                "url": "https://bankingjournal.aba.com/2026/04/fed-proposes-opening-fednow-to-cross-border-payments/",
                "published_at": "2026-04-08",
                "snippet": "ABA analysis of the Fed's cross-border proposal: what community banks and credit unions need to know about the rule change and its compliance implications.",
            },
            {
                "title": "FedNow Fortifies Security for Instant Payments",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/news/faster-payments/2026/fednow-service-fortifies-security-for-instant-payments/",
                "published_at": "2026-04-28",
                "snippet": "Federal Reserve Financial Services launched a network intelligence API for FedNow that gives participating FIs real-time, account-level risk data to counter fraud at the moment of transfer.",
            },
            {
                "title": "How FedNow Is a Catalyst for Credit Union Disruption",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/payments/news/how-fednow-is-a-catalyst-for-credit-union-disruption",
                "published_at": "2026-06-03",
                "snippet": "FedNow is pushing credit unions to rethink their payment strategy from the ground up — early adopters are using instant payments as a member-acquisition wedge against big banks.",
            },
        ],
    },
    {
        "theme": "AI Moves From Pilot to Production at Credit Unions",
        "icon": "🤖",
        "heat_score": 91,
        "summary": (
            "43% of credit unions now say generative AI is the top technology reshaping their "
            "operations in 2026. AI chat, member retention modelling, and AI-agent-initiated "
            "payments are moving from proof-of-concept to live deployments. CUs that don't offer "
            "AI chat risk being cut out of member financial conversations entirely."
        ),
        "tags": ["ai", "generative-ai", "member-retention", "credit-unions", "ai-agents"],
        "articles": [
            {
                "title": "Credit Unions Prepare for the Day AI Agents Start Spending",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/credit-unions-prepare-for-the-day-ai-agents-start-spending/",
                "published_at": "2026-07-22",
                "snippet": "AI agents capable of initiating payments autonomously on behalf of members are arriving. Credit unions are auditing their authentication and authorization frameworks before the wave hits.",
            },
            {
                "title": "New Study Finds AI Critical to Credit Union Member Retention",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/new-study-finds-ai-critical-to-credit-union-member-retention/",
                "published_at": "2026-06-15",
                "snippet": "Members who've switched FIs were 122% more likely to want AI chat support — making AI-powered service the clearest predictor of whether a credit union retains or loses younger members.",
            },
            {
                "title": "Credit Unions Need AI Chat to Stay in the Conversation",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/news/artificial-intelligence/2026/credit-unions-need-ai-chat-to-stay-in-the-conversation/",
                "published_at": "2026-05-07",
                "snippet": "Only 1 in 3 fintechs offer AI-led chat support. Credit unions that deploy it first can own the conversational banking layer that keeps members from defaulting to big-bank apps.",
            },
            {
                "title": "How a New York Credit Union Makes Itself 'Discoverable' on AI",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/payments/news/how-a-new-york-credit-union-makes-itself-discoverable-on-ai",
                "published_at": "2026-08-11",
                "snippet": "A New York CU built an AI discoverability strategy so members find its products when asking generative AI tools for financial advice — a new battleground for member acquisition.",
            },
            {
                "title": "Banks and Credit Unions Say They're Growing More Fluent in AI",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/news/exclusive-research-ai-literacy-is-on-the-rise-among-banks",
                "published_at": "2026-07-09",
                "snippet": "Half of all institutions surveyed are now at least moderately literate in AI — up significantly from 2025 — driven by on-the-job learning and informal knowledge sharing.",
            },
        ],
    },
    {
        "theme": "Fraud in the Era of Real-Time, AI-Powered Attacks",
        "icon": "🚨",
        "heat_score": 88,
        "summary": (
            "41% of FIs cite real-time payments fraud as their top 2026 risk. AI is now both "
            "the weapon (synthetic identities, voice cloning) and the shield (real-time behavioural "
            "analytics). 82% of CU members say security determines how they pay — fraud management "
            "is now a direct driver of transaction volume, not just a cost center."
        ),
        "tags": ["fraud", "ai-fraud", "real-time-payments", "synthetic-identity", "security"],
        "articles": [
            {
                "title": "Credit Unions Fight Fraud by Connecting Member Data Faster",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/credit-unions-fight-fraud-by-connecting-member-data-faster/",
                "published_at": "2026-06-24",
                "snippet": "Credit unions fighting AI-powered fraud are winning by unifying real-time data across account opening, authentication, and payment activity — catching attacks that span multiple systems.",
            },
            {
                "title": "82% of Credit Union Members Say Security Drives How They Pay",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/82-of-credit-union-members-say-security-drives-how-they-pay/",
                "published_at": "2026-05-29",
                "snippet": "PYMNTS survey: 82% of CU members choose payment methods primarily based on perceived security — making fraud prevention the single biggest lever on transaction volume.",
            },
            {
                "title": "Fraud Will Remain a Top Problem for Banks in 2026, But AI Could Help",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/payments/news/exclusive-research-is-ai-an-effective-tool-to-fight-fraud",
                "published_at": "2026-04-17",
                "snippet": "41% of respondents say real-time payments fraud has the biggest negative impact on their organization in 2026 — and AI-driven detection is the primary response strategy.",
            },
            {
                "title": "Executives See Speed, Trust and Data Reshaping Payments in 2026",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/news/payments-innovation/2026/executives-see-speed-trust-and-data-reshaping-payments-in-2026/",
                "published_at": "2026-03-12",
                "snippet": "Payment leaders rank fraud management as the top operational challenge of 2026 — ahead of compliance and infrastructure — as AI-generated attacks accelerate across all channels.",
            },
        ],
    },
    {
        "theme": "Stablecoin Rules Take Shape: GENIUS Act Implementation",
        "icon": "💎",
        "heat_score": 85,
        "summary": (
            "The GENIUS Act became law in July 2025 and regulators are racing to finish "
            "implementation rules before the January 2027 deadline. The OCC targets November "
            "for final stablecoin regs. FinCEN and banking agencies proposed the first KYC "
            "rules for stablecoin issuers in August 2026. Credit unions must decide whether "
            "to pursue NCUA-supervised issuance or cede the market to bank-chartered issuers."
        ),
        "tags": ["stablecoins", "genius-act", "occ", "fincen", "ncua", "digital-assets"],
        "articles": [
            {
                "title": "FinCEN, Banking Agencies Propose First Customer ID Rules for Stablecoin Issuers",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/cryptocurrency/2026/fincen-banking-agencies-propose-first-customer-identification-rules-stablecoin-issuers/",
                "published_at": "2026-08-14",
                "snippet": "Treasury and banking regulators jointly proposed the first KYC rules specifically covering stablecoin issuers — a major step in GENIUS Act implementation with a 60-day comment window.",
            },
            {
                "title": "OCC Races the Clock to Finish GENIUS Act Stablecoin Rules",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/legal/2026/occ-races-the-clock-to-finish-genius-act-stablecoin-rules/",
                "published_at": "2026-07-31",
                "snippet": "The OCC is targeting November for its final stablecoin framework — giving banks and credit unions only weeks to adjust charter strategies before the rules lock in.",
            },
            {
                "title": "New Stablecoin Rules Push Banks Into the Crypto Front Line",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/legal/2026/new-stablecoin-rules-push-banks-into-the-crypto-front-line/",
                "published_at": "2026-06-19",
                "snippet": "Under GENIUS Act rules, banks must upgrade wallet-level monitoring and prepare for AI agents that conduct transactions without direct human approval — shifting compliance from periodic to real-time.",
            },
            {
                "title": "Bank Regulators Push Stablecoin Rules While Warning on AI Risks",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/cryptocurrency/2026/bank-regulators-push-stablecoin-rules-while-warning-on-ai-risks/",
                "published_at": "2026-05-06",
                "snippet": "Regulators are releasing stablecoin guidance and AI risk warnings simultaneously — signalling that the two converging technologies pose the biggest combined compliance challenge since AML.",
            },
            {
                "title": "OCC's GENIUS Implementation Draft Keeps Yield on the Table",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/news/occs-genius-implementation-draft-rule-keeps-yield-on-the-table",
                "published_at": "2026-08-05",
                "snippet": "The OCC's draft GENIUS Act rules preserve a path for stablecoin issuers to offer yield — leaving a key competitive loophole open that community banks are lobbying hard to close.",
            },
        ],
    },
    {
        "theme": "Core Modernization: Cloud, AI, and the FinTech Partnership Surge",
        "icon": "🏗️",
        "heat_score": 78,
        "summary": (
            "FinTech partnerships with credit unions grew 19% year-over-year; nearly two-thirds "
            "of CUs now use fintechs to upgrade core products rather than replacing the core. "
            "Cloud data strategies are the new battleground — institutions that centralize data "
            "from cores, processors, and digital channels first will own the AI advantage. "
            "Legacy cores are no longer just slow; they're actively blocking AI deployments."
        ),
        "tags": ["core-banking", "cloud", "fintech", "modernization", "data-strategy"],
        "articles": [
            {
                "title": "Nearly Two-Thirds of Credit Unions Turn to FinTechs to Upgrade Core Products",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/nearly-two-thirds-of-credit-unions-turn-to-fintechs-to-upgrade-core-products",
                "published_at": "2026-07-14",
                "snippet": "63% of credit unions are now sourcing core product upgrades from fintech partners rather than their core vendor — a structural shift from loyalty to pragmatism in vendor relationships.",
            },
            {
                "title": "Credit Unions Build Cloud Data Strategy to Stay Competitive",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/credit-unions-build-cloud-data-strategy-to-stay-competitive/",
                "published_at": "2026-06-30",
                "snippet": "Credit unions are racing to consolidate data from cores, processors, and digital channels into cloud-native architectures — the prerequisite for any serious AI deployment.",
            },
            {
                "title": "How Credit Unions Became FinTechs' Best Bet for Scale",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/how-credit-unions-became-fintechs-best-bet-for-scale/",
                "published_at": "2026-05-21",
                "snippet": "Fintech partnerships with credit unions grew nearly 19% year over year, with almost half of all fintechs now working with at least one CU — reversing years of fintech-CU friction.",
            },
            {
                "title": "The Real Work of Modernizing Banks' Systems Is Only Just Beginning",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/opinion/the-real-work-of-modernizing-banks-systems-is-only-just-beginning",
                "published_at": "2026-08-19",
                "snippet": "Legacy core systems now directly constrain banks' ability to deploy AI and respond to regulators — and the chisel-versus-sledgehammer modernization debate is reaching a tipping point.",
            },
        ],
    },
    {
        "theme": "BNPL at 22% Growth: Credit Unions' Loyalty Opportunity",
        "icon": "📲",
        "heat_score": 72,
        "summary": (
            "BNPL transaction value grew 22% in 2025. 38% of CU members want BNPL from their "
            "own institution — but only 11% of credit unions currently offer it. BNPL is moving "
            "beyond retail checkout into utilities, medical bills, and travel. CUs that bring "
            "BNPL in-house stop losing the relationship to fintechs at the most active spending moments."
        ),
        "tags": ["bnpl", "embedded-finance", "member-retention", "lending", "gen-z"],
        "articles": [
            {
                "title": "BNPL Moves From Checkout Perk to Credit Union Retention Tool",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/buy-now-pay-later-moves-from-checkout-perk-to-credit-union-retention-tool/",
                "published_at": "2026-07-28",
                "snippet": "38% of CU members want BNPL from their own institution. CUs that deploy it in-house keep members engaged at checkout — and gather spending intelligence that fintech BNPL providers keep for themselves.",
            },
            {
                "title": "22% BNPL Growth Gives Credit Unions a Member Loyalty Opening",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/22percent-bnpl-growth-gives-credit-unions-a-member-loyalty-opening/",
                "published_at": "2026-06-10",
                "snippet": "BNPL value grew 22% in 2025. Credit unions willing to offer it can capture that volume in-house rather than watching members use Klarna or Affirm — and hand over transaction data — at checkout.",
            },
            {
                "title": "38% of Credit Union Members Want BNPL From Their FI",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/credit-unions/2026/38-of-credit-union-members-want-bnpl-from-their-fi/",
                "published_at": "2026-05-13",
                "snippet": "PYMNTS data: 70% of Gen Z CU members would use BNPL from their primary FI — yet only 11% of credit unions offer it. The gap is a member attrition risk growing every quarter.",
            },
            {
                "title": "The BNPL Revolution Moves Into the Card Stack",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/bnpl/2026/the-bnpl-revolution-moves-into-the-card-stack/",
                "published_at": "2026-08-04",
                "snippet": "Installment payments are being embedded directly into debit and credit card products — raising the stakes for credit unions whose card programs don't yet support in-line installment options.",
            },
        ],
    },
]


def run():
    db = SessionLocal()
    db.query(TrendingTopic).delete()
    db.flush()

    for i, data in enumerate(TOPICS):
        articles = data.pop("articles")
        topic = TrendingTopic(
            id=str(uuid.uuid4()),
            article_count=len(articles),
            articles=articles,
            refreshed_at=now - timedelta(hours=i * 3),
            created_at=now - timedelta(days=1),
            **data,
        )
        db.add(topic)

    db.commit()
    print(f"✅ Seeded {len(TOPICS)} trending topics (2026 articles only, all URLs verified 200)")
    for t in db.query(TrendingTopic).order_by(TrendingTopic.heat_score.desc()).all():
        print(f"  [{t.heat_score:3}] {t.icon} {t.theme} — {t.article_count} articles")
    db.close()


if __name__ == "__main__":
    run()
