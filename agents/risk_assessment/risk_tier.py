"""
Module:  risk_tier.py
Agent:   Risk Assessment Agent
Purpose: Company size tier classification and materiality-adjusted point scoring.
         Provides tier-based multipliers so the same raw finding has
         proportionally less impact on a mega-cap vs. a micro-cap.
         Universal Red Flags bypass multipliers and always fire at full points.
         
# Hinglish Summary:
# Ye module company ki size ke hisab se usko ek 'Tier' (jaise MEGA, SMALL) deta hai.
# Fir usi tier ke hisab se risk points ko kam ya zyada (multiply) karta hai.
# Jaise agar badi company (MEGA) hai toh choti problems ko kam point diye jayenge, 
# lekin agar fraud (Universal Red Flag) hai, toh full points diye jayenge chahe company kitni bhi badi ho.
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tier definitions  (market_cap_min_USD, revenue_min_USD, multiplier)
# ---------------------------------------------------------------------------
TIER_THRESHOLDS = [
    ("MEGA",  200_000_000_000, 50_000_000_000,  0.40),
    ("LARGE",  10_000_000_000,  5_000_000_000,  0.60),
    ("MID",     2_000_000_000,  1_000_000_000,  1.00),
    ("SMALL",     250_000_000,    100_000_000,  1.30),
    ("MICRO",               0,              0,  1.60),
]

TIER_MULTIPLIERS: dict[str, float] = {t[0]: t[3] for t in TIER_THRESHOLDS}

# ---------------------------------------------------------------------------
# Universal Red Flags — exempt from tier multipliers
# ---------------------------------------------------------------------------
UNIVERSAL_RED_FLAG_RULES: set[str] = {
    "beneish_likely_manipulator",
    "altman_distress_zone",
    "fcf_negative_consecutive",
    "SEC_DOJ_FORMAL",
    "8K_FRAUD_KEYWORD",
    "DUAL_CEO_CFO_DEPARTURE",
    "compound_distress",
}

# Crisis keywords in headlines that are ALWAYS size-invariant
UNIVERSAL_CRISIS_KEYWORDS: set[str] = {
    "fraud", "criminal", "sec investigation", "doj investigation",
    "restatement", "restated", "bankruptcy", "whistleblower",
    "sanctions violation", "going concern", "material weakness",
    "sec enforcement", "wells notice", "indicted", "arrested",
}

# Validated regulator whitelist — filters LLM hallucinations
VALID_REGULATORS: set[str] = {
    "SEC", "DOJ", "FTC", "FDA", "EPA", "IRS", "CFPB", "FINRA",
    "CFTC", "OCC", "FDIC", "OFAC", "IDPC", "EU COMMISSION", "FCA",
    "NLRB", "OSHA", "EEOC", "COURT OF APPEALS",
    "DEPARTMENT OF JUSTICE", "SECURITIES AND EXCHANGE COMMISSION",
    "FEDERAL TRADE COMMISSION", "FOOD AND DRUG ADMINISTRATION",
    "INTERNAL REVENUE SERVICE", "FINANCIAL INDUSTRY REGULATORY AUTHORITY",
    "CONSUMER FINANCIAL PROTECTION BUREAU",
    "PCAOB", "PUBLIC COMPANY ACCOUNTING OVERSIGHT BOARD",
    "DPC", "DATA PROTECTION COMMISSION",
    "DELOITTE", "PWC", "EY", "KPMG", "COSO",
    "COMMITTEE OF SPONSORING ORGANIZATIONS",
}

# Executive departure thresholds (elevated, critical) by tier
DEPARTURE_THRESHOLDS: dict[str, tuple[int, int]] = {
    "MEGA":  (7, 10),
    "LARGE": (5,  7),
    "MID":   (4,  5),
    "SMALL": (3,  4),
    "MICRO": (2,  3),
}


def classify_tier(market_cap, revenue) -> str:
    """
    # Ye function company ki Market Cap aur Revenue dekh kar uska Tier decide karta hai.
    # Agar data nahi milta toh safely 'MID' tier assume kar leta hai.
    """
    cap = float(market_cap) if market_cap and market_cap > 0 else None
    rev = float(revenue)    if revenue    and revenue    > 0 else None

    if cap is not None:
        for tier, cap_min, _, _ in TIER_THRESHOLDS:
            if cap >= cap_min:
                logger.info("[CompanyTier] %s via market_cap", tier)
                return tier
    if rev is not None:
        for tier, _, rev_min, _ in TIER_THRESHOLDS:
            if rev >= rev_min:
                logger.info("[CompanyTier] %s via revenue", tier)
                return tier

    logger.info("[CompanyTier] Defaulting to MID tier")
    return "MID"


def get_multiplier(tier: str) -> float:
    """Return the risk point multiplier for the given tier."""
    return TIER_MULTIPLIERS.get(tier, 1.0)


def adjust_points(base_points: int, tier: str,
                  is_red_flag: bool = False,
                  extra_multiplier: float = 1.0) -> int:
    """
    # Ye function base risk points ko company tier ke hisab se adjust karta hai.
    # Agar 'is_red_flag' True hai, toh multiplier ko bypass karke direct base points return karta hai (Kyuki Red flag chota bada nahi hota).
    """
    if is_red_flag:
        return max(0, base_points)
    mult = get_multiplier(tier) * extra_multiplier
    return max(0, round(base_points * mult))


def is_universal_red_flag(rule_name: str) -> bool:
    return rule_name in UNIVERSAL_RED_FLAG_RULES


def is_crisis_keyword_universal(headline: str) -> bool:
    """True if headline contains a size-invariant crisis keyword."""
    hl = headline.lower()
    return any(kw in hl for kw in UNIVERSAL_CRISIS_KEYWORDS)


def is_valid_regulator(name: str) -> bool:
    """True if the LLM-returned regulator name matches our whitelist."""
    upper = name.upper().strip()
    if upper in VALID_REGULATORS:
        return True
    for valid in VALID_REGULATORS:
        if valid in upper:
            return True
    return False


def get_departure_thresholds(tier: str) -> tuple[int, int]:
    """Return (elevated_threshold, critical_threshold) for exec departures."""
    return DEPARTURE_THRESHOLDS.get(tier, DEPARTURE_THRESHOLDS["MID"])
