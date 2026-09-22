"""
seed_trending.py
=================
Seeds realistic fintech trending topics with grouped themes and article links.
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
        "theme": "FedNow Surges Past 1,000 Participants",
        "icon": "⚡",
        "heat_score": 96,
        "summary": (
            "FedNow has crossed 1,200 live financial institutions — doubling in 12 months. "
            "Credit unions are now leading adoption by volume, with 40% of new live participants "
            "being community banks and CUs under $5B in assets. Instant payment volumes hit a "
            "record $3.2B in August alone."
        ),
        "tags": ["fednow", "real-time-payments", "credit-unions", "infrastructure"],
        "articles": [
            {
                "title": "FedNow Surpasses 1,200 Participants as Credit Union Adoption Accelerates",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/news/faster-payments/2026/fednow-surpasses-1200-participants-credit-union-adoption/",
                "published_at": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
                "snippet": "The Federal Reserve's instant payment service now counts over 1,200 financial institutions, with credit unions making up nearly 35% of new additions in Q3.",
            },
            {
                "title": "FedNow vs. RTP: Where Financial Institutions Are Placing Their Bets in 2026",
                "source": "The Financial Brand",
                "url": "https://thefinancialbrand.com/news/payments-trends/fednow-rtp-financial-institutions-2026/",
                "published_at": (now - timedelta(days=4)).strftime("%Y-%m-%d"),
                "snippet": "A new survey finds 68% of community banks and credit unions plan to go live on at least one real-time rail by Q4 2026 — up from 41% last year.",
            },
            {
                "title": "How Alliant Credit Union Cut Payment Processing Costs 40% with FedNow",
                "source": "Payments Journal",
                "url": "https://www.paymentsjournal.com/alliant-credit-union-fednow-cost-reduction/",
                "published_at": (now - timedelta(days=6)).strftime("%Y-%m-%d"),
                "snippet": "Alliant's treasury team shares how consolidating four vendor relationships onto a single payment hub delivered unexpected savings beyond just faster rails.",
            },
            {
                "title": "The Fed Publishes FedNow 2027 Roadmap: Request-to-Pay, Alias Directory Next",
                "source": "Finextra",
                "url": "https://www.finextra.com/newsarticle/fednow-2027-roadmap-request-to-pay/",
                "published_at": (now - timedelta(days=8)).strftime("%Y-%m-%d"),
                "snippet": "The Federal Reserve has published its multi-year FedNow feature roadmap, signaling upcoming additions including request-to-pay and a shared alias directory with RTP.",
            },
            {
                "title": "Credit Unions Under $1B Now Biggest FedNow Growth Segment, Says Fed Data",
                "source": "CUNA News",
                "url": "https://news.cuna.org/articles/fednow-growth-credit-unions-under-1b/",
                "published_at": (now - timedelta(days=10)).strftime("%Y-%m-%d"),
                "snippet": "Federal Reserve data shows that the fastest growing FedNow adopter segment is credit unions with assets between $500M and $1B — driven by competitive pressure from digital banks.",
            },
        ],
    },
    {
        "theme": "AI in Banking: From Chatbots to Underwriting",
        "icon": "🤖",
        "heat_score": 91,
        "summary": (
            "Generative AI is moving from pilot to production across lending, fraud detection, "
            "and member service. Banks deploying AI underwriting report 30–45% faster loan "
            "decisions. Regulators are playing catch-up — the OCC issued new AI model risk "
            "guidance this quarter that's reshaping vendor evaluations."
        ),
        "tags": ["ai", "generative-ai", "underwriting", "fraud", "regulation"],
        "articles": [
            {
                "title": "OCC Issues New AI Model Risk Management Guidance for Banks",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/news/occ-ai-model-risk-management-guidance-2026/",
                "published_at": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                "snippet": "The Office of the Comptroller issued updated guidance requiring banks to document AI model lineage, bias testing, and explainability — with a 180-day compliance window.",
            },
            {
                "title": "Navy Federal Deploys AI Underwriting, Cuts Decision Time to Under 4 Minutes",
                "source": "The Financial Brand",
                "url": "https://thefinancialbrand.com/news/artificial-intelligence/navy-federal-ai-underwriting-4-minutes/",
                "published_at": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
                "snippet": "Navy Federal Credit Union's AI-assisted personal loan underwriting has reduced average decision time from 2.1 days to under 4 minutes while maintaining approval accuracy.",
            },
            {
                "title": "Gen AI Fraud Detection: Credit Unions Report 52% Reduction in False Positives",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/fraud-prevention/2026/generative-ai-credit-unions-false-positive-reduction/",
                "published_at": (now - timedelta(days=5)).strftime("%Y-%m-%d"),
                "snippet": "A PYMNTS survey of 120 credit unions found that those using generative AI for transaction monitoring saw a median 52% drop in false-positive fraud alerts.",
            },
            {
                "title": "The Hidden Risk in AI Banking: Why 43% of Pilots Never Reach Production",
                "source": "Finextra",
                "url": "https://www.finextra.com/blogposting/ai-banking-pilots-production-gap/",
                "published_at": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
                "snippet": "A new Finextra report identifies data quality, model governance gaps, and compliance uncertainty as the top barriers preventing AI pilots from reaching live deployment.",
            },
        ],
    },
    {
        "theme": "Stablecoins Enter the Mainstream",
        "icon": "💎",
        "heat_score": 85,
        "summary": (
            "The GENIUS Act stablecoin framework is advancing through Congress, and major banks "
            "are moving fast. JPMorgan expanded JPM Coin to retail B2B, while three top-10 banks "
            "announced stablecoin pilots for cross-border supplier payments. Credit unions are "
            "watching closely — NCUA has not yet issued stablecoin guidance."
        ),
        "tags": ["stablecoins", "cbdc", "digital-assets", "genius-act", "regulation"],
        "articles": [
            {
                "title": "GENIUS Act Advances: What the Stablecoin Framework Means for Banks and Credit Unions",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/news/genius-act-stablecoin-framework-banks-credit-unions/",
                "published_at": (now - timedelta(days=3)).strftime("%Y-%m-%d"),
                "snippet": "The Guiding and Establishing National Innovation for US Stablecoins (GENIUS) Act moved to the Senate floor, creating a federal licensing framework that would let banks issue dollar-backed stablecoins.",
            },
            {
                "title": "JPMorgan Expands JPM Coin to SMB Cross-Border Payments",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/cryptocurrency/2026/jpmorgan-jpm-coin-smb-cross-border-payments/",
                "published_at": (now - timedelta(days=5)).strftime("%Y-%m-%d"),
                "snippet": "JPMorgan has broadened access to JPM Coin, its permissioned stablecoin, to small and mid-size business cross-border payments — processing over $12B in daily volume.",
            },
            {
                "title": "NCUA Silent on Stablecoins as Credit Unions Ask for Clarity",
                "source": "CUNA News",
                "url": "https://news.cuna.org/articles/ncua-stablecoin-guidance-credit-unions-waiting/",
                "published_at": (now - timedelta(days=9)).strftime("%Y-%m-%d"),
                "snippet": "Credit union executives are asking the NCUA for stablecoin-specific guidance as member demand for digital-asset services grows — the agency says it is 'monitoring developments.'",
            },
            {
                "title": "Visa and Mastercard Accelerate Stablecoin Settlement Pilots with Community Banks",
                "source": "Payments Journal",
                "url": "https://www.paymentsjournal.com/visa-mastercard-stablecoin-settlement-community-banks/",
                "published_at": (now - timedelta(days=11)).strftime("%Y-%m-%d"),
                "snippet": "Both networks are running stablecoin settlement pilots with select community bank partners, using USDC on Ethereum to reduce overnight settlement risk.",
            },
        ],
    },
    {
        "theme": "Core Modernization: The Tipping Point",
        "icon": "🏗️",
        "heat_score": 78,
        "summary": (
            "After years of reluctance, credit unions and community banks are finally pulling "
            "the trigger on core replacements — or finding middleware strategies to extend legacy "
            "cores. Fiserv and Jack Henry are both under pressure as cloud-native cores like "
            "Temenos and Mambu gain ground. Key driver: FedNow and real-time rails expose core "
            "latency limitations that can't be patched."
        ),
        "tags": ["core-banking", "modernization", "fiserv", "jack-henry", "cloud"],
        "articles": [
            {
                "title": "Why 2026 Is the Year Credit Unions Finally Replace Their Cores",
                "source": "The Financial Brand",
                "url": "https://thefinancialbrand.com/news/core-banking/credit-unions-core-replacement-2026/",
                "published_at": (now - timedelta(days=2)).strftime("%Y-%m-%d"),
                "snippet": "Real-time payment demands and digital member expectations have made legacy cores untenable for a growing number of mid-size credit unions. Here's what's driving the shift.",
            },
            {
                "title": "Jack Henry Faces Pressure as Cloud-Native Cores Poach Credit Union Clients",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/news/jack-henry-pressure-cloud-native-cores-credit-unions/",
                "published_at": (now - timedelta(days=6)).strftime("%Y-%m-%d"),
                "snippet": "Three credit unions announced departures from Jack Henry's Symitar platform in Q3, citing API limitations and real-time payment onboarding timelines of 18+ months.",
            },
            {
                "title": "The Middleware Escape Hatch: How CUs Are Extending Legacy Cores for a Decade More",
                "source": "Payments Journal",
                "url": "https://www.paymentsjournal.com/middleware-strategy-credit-union-legacy-core/",
                "published_at": (now - timedelta(days=8)).strftime("%Y-%m-%d"),
                "snippet": "Rather than replacing their core, a growing cohort of credit unions is deploying payment middleware and API layers — buying time without a multi-year conversion project.",
            },
            {
                "title": "Temenos Reports 300% YoY Growth in North American Credit Union Pipeline",
                "source": "Finextra",
                "url": "https://www.finextra.com/newsarticle/temenos-north-america-credit-union-growth/",
                "published_at": (now - timedelta(days=14)).strftime("%Y-%m-%d"),
                "snippet": "Temenos cited North American credit unions as its fastest-growing segment, attributing the growth to dissatisfaction with legacy core vendors and demand for real-time payment capabilities.",
            },
        ],
    },
    {
        "theme": "Embedded Finance & BNPL Pressure on CUs",
        "icon": "📲",
        "heat_score": 72,
        "summary": (
            "Buy-now-pay-later adoption continues to eat into credit union personal loan portfolios. "
            "Embedded finance — lending and payments built into merchant checkout — now accounts for "
            "an estimated $180B in consumer credit. Credit unions that can't offer real-time loan "
            "decisioning at the point of sale are losing younger members to fintechs."
        ),
        "tags": ["bnpl", "embedded-finance", "lending", "consumer-credit", "fintech"],
        "articles": [
            {
                "title": "BNPL Now Accounts for 8% of US E-Commerce — Up From 2% in 2021",
                "source": "PYMNTS",
                "url": "https://www.pymnts.com/buy-now-pay-later/2026/bnpl-ecommerce-share-8-percent/",
                "published_at": (now - timedelta(days=4)).strftime("%Y-%m-%d"),
                "snippet": "New PYMNTS data shows BNPL's share of US e-commerce reached 8%, largely at the expense of credit card revolving balances — and credit union personal loans.",
            },
            {
                "title": "Credit Unions Are Losing Gen Z Borrowers to BNPL — Here's How to Fight Back",
                "source": "The Financial Brand",
                "url": "https://thefinancialbrand.com/news/lending/credit-unions-gen-z-bnpl-competition/",
                "published_at": (now - timedelta(days=7)).strftime("%Y-%m-%d"),
                "snippet": "A Credit Union Times analysis found that credit unions with real-time loan decisioning retained 31% more Gen Z members than peers still using 24-48 hour approval processes.",
            },
            {
                "title": "CFPB Proposes BNPL Oversight Rules That Could Level the Playing Field for CUs",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/news/cfpb-bnpl-oversight-rules-credit-unions/",
                "published_at": (now - timedelta(days=10)).strftime("%Y-%m-%d"),
                "snippet": "Proposed CFPB rules would require BNPL providers to apply the same disclosure and dispute standards as credit cards — potentially reducing the compliance advantage fintechs have held.",
            },
        ],
    },
    {
        "theme": "Fraud Surge: Real-Time Payments, Real-Time Risk",
        "icon": "🚨",
        "heat_score": 88,
        "summary": (
            "The irrevocable nature of real-time payments has created a fraud epidemic. "
            "Authorized push payment (APP) fraud losses hit $2.9B in H1 2026. "
            "UK-style mandatory reimbursement rules are now under active discussion at the CFPB, "
            "which would shift liability from consumers back to financial institutions. "
            "Credit unions with RTP/FedNow exposure need fraud tooling upgrades urgently."
        ),
        "tags": ["fraud", "app-fraud", "real-time-payments", "risk", "cfpb"],
        "articles": [
            {
                "title": "APP Fraud Losses Reach $2.9B in H1 2026 as Real-Time Payments Expand",
                "source": "Payments Journal",
                "url": "https://www.paymentsjournal.com/app-fraud-2-9-billion-real-time-payments-2026/",
                "published_at": (now - timedelta(days=1)).strftime("%Y-%m-%d"),
                "snippet": "Authorized push payment fraud continued its steep climb in the first half of 2026, with losses up 34% YoY as adoption of FedNow and RTP broadens the attack surface.",
            },
            {
                "title": "CFPB Signals Interest in UK-Style APP Fraud Reimbursement Rules for US",
                "source": "American Banker",
                "url": "https://www.americanbanker.com/news/cfpb-app-fraud-reimbursement-rules-uk-model/",
                "published_at": (now - timedelta(days=4)).strftime("%Y-%m-%d"),
                "snippet": "CFPB Director stated the bureau is 'closely studying' the UK's mandatory reimbursement model for APP fraud, which shifted $600M in liability from consumers to banks in 2024.",
            },
            {
                "title": "How BECU Built a Real-Time Fraud Layer on Top of FedNow Without Slowing Payments",
                "source": "Finextra",
                "url": "https://www.finextra.com/blogposting/becu-fednow-real-time-fraud-layer/",
                "published_at": (now - timedelta(days=6)).strftime("%Y-%m-%d"),
                "snippet": "BECU's payments engineering team shares how they implemented a machine-learning fraud scoring layer that adds sub-50ms latency to FedNow transactions.",
            },
            {
                "title": "Zelle Fraud Settlements Prompt CUs to Re-examine Instant Payment Liability Policies",
                "source": "CUNA News",
                "url": "https://news.cuna.org/articles/zelle-fraud-settlements-credit-union-liability/",
                "published_at": (now - timedelta(days=9)).strftime("%Y-%m-%d"),
                "snippet": "Following high-profile Zelle fraud settlements, credit union compliance officers are reviewing member agreements and fraud reimbursement thresholds for all real-time payment channels.",
            },
        ],
    },
]


def run():
    db = SessionLocal()

    # Clear existing topics
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
    print(f"✅ Seeded {len(TOPICS)} trending topics")
    for t in db.query(TrendingTopic).order_by(TrendingTopic.heat_score.desc()).all():
        print(f"  [{t.heat_score:3}] {t.icon} {t.theme} — {t.article_count} articles")
    db.close()


if __name__ == "__main__":
    run()
