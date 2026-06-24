"""
FintelliPro — NCUA Schema Auto-Detection
==========================================
Instead of hardcoding column names, this module probes the actual
columns present in any NCUA quarterly ZIP and builds a mapping
dynamically. This means the parser works even when NCUA changes
column names, adds new files, or restructures the ZIP.

How it works:
1. Read AcctDesc.txt (ships in every NCUA ZIP) — maps ACCT_ codes
   to human descriptions like "Total Assets" or "Number of Members"
2. Find the right columns by searching descriptions, not hardcoded names
3. Fall back to known-stable column names if descriptions change
4. Emit a structured SchemaMap that all parsers use
"""

import re
import csv
import io
from dataclasses import dataclass, field
from loguru import logger


@dataclass
class NCUASchemaMap:
    """
    Maps our logical field names → actual column names found in this ZIP.
    Built fresh each quarter by probing the real file contents.
    """
    quarter: str = ""

    # FOICU.txt columns (identity / directory data)
    col_cu_number:   str = "CU_NUMBER"
    col_cu_name:     str = "CU_NAME"
    col_city:        str = "CITY"
    col_state:       str = "STATE"
    col_zip:         str = "ZIP_CODE"
    col_cu_type:     str = "CU_TYPE"
    col_licu:        str = "LIMITED_INC"
    col_tom_code:    str = "TOM_CODE"

    # FS220.txt columns (financial data) — ACCT_ codes are stable
    col_assets:      str = "ACCT_010"     # Total assets
    col_loans:       str = "ACCT_025B"    # Total loans outstanding
    col_shares:      str = "ACCT_657"     # Total shares/deposits
    col_members:     str = "ACCT_730"     # Number of members
    col_net_worth:   str = "ACCT_940"     # Total net worth
    col_net_income:  str = "ACCT_902"     # Net income YTD
    col_branches_a:  str = "ACCT_741A"    # Main office count
    col_branches_b:  str = "ACCT_741B1"   # Branch count

    # Validation results
    foicu_cols_found:  list = field(default_factory=list)
    fs220_cols_found:  list = field(default_factory=list)
    missing_cols:      list = field(default_factory=list)
    warnings:          list = field(default_factory=list)


# ── Keyword mappings to find columns by description ────────────
# If NCUA ever renames ACCT_010, we can find it by its description
FINANCIAL_FIELD_KEYWORDS = {
    "assets":     [("ACCT_010",), ("total assets", "total asset")],
    "loans":      [("ACCT_025B",), ("total loans", "loan outstanding")],
    "shares":     [("ACCT_657",), ("total shares", "total deposit", "shares and deposit")],
    "members":    [("ACCT_730",), ("number of members", "total members", "membership")],
    "net_worth":  [("ACCT_940",), ("total net worth", "net worth total", "equity")],
    "net_income": [("ACCT_902",), ("net income", "net earnings")],
}

# Fallback column name candidates in priority order
FOICU_FALLBACKS = {
    "cu_number": ["CU_NUMBER", "CU_NBR", "CHARTER_NUMBER", "CuNumber"],
    "cu_name":   ["CU_NAME", "NAME", "CuName", "CREDIT_UNION_NAME"],
    "city":      ["CITY", "CITY_NAME", "CuCity"],
    "state":     ["STATE", "STATE_CODE", "ST", "CharterState"],
    "zip":       ["ZIP_CODE", "ZIP", "ZIPCODE"],
    "cu_type":   ["CU_TYPE", "CHARTER_TYPE", "CU_TYPE_CODE"],
    "licu":      ["LIMITED_INC", "LOW_INCOME", "LICU", "LI_DESIGNATION"],
    "tom_code":  ["TOM_CODE", "TYPE_OF_MEMBERSHIP", "FOM_TYPE"],
}


def probe_foicu_schema(foicu_rows: list[dict]) -> dict:
    """
    Auto-detect FOICU.txt column names by trying known variants.
    Returns dict: logical_name -> actual_column_name
    """
    if not foicu_rows:
        return {}

    actual_cols = set(foicu_rows[0].keys())
    mapping = {}

    for logical, candidates in FOICU_FALLBACKS.items():
        found = next((c for c in candidates if c in actual_cols), None)
        if found:
            mapping[logical] = found
        else:
            logger.warning(f"FOICU: could not find column for '{logical}'. "
                           f"Tried: {candidates}. Available: {sorted(actual_cols)[:10]}")
            mapping[logical] = candidates[0]  # use default even if missing

    return mapping


def probe_fs220_schema(fs220_rows: list[dict], acct_desc: dict) -> dict:
    """
    Auto-detect FS220.txt column names.

    Strategy:
    1. Try known stable ACCT_ codes first (they rarely change)
    2. Fall back to searching AcctDesc.txt by keyword
    3. Log a warning if neither works (alerts us to schema change)
    """
    if not fs220_rows:
        return {}

    actual_cols = set(fs220_rows[0].keys())
    mapping = {}

    for logical, (primary_codes, keywords) in FINANCIAL_FIELD_KEYWORDS.items():
        # Try primary known codes first
        found = next((c for c in primary_codes if c in actual_cols), None)

        if found:
            mapping[logical] = found
        else:
            # Search AcctDesc.txt for a column matching the keywords
            match = _find_col_by_description(actual_cols, acct_desc, keywords)
            if match:
                mapping[logical] = match
                logger.warning(
                    f"FS220: '{logical}' primary col {primary_codes} not found — "
                    f"using '{match}' found via description search. "
                    f"NCUA may have renamed this column."
                )
            else:
                mapping[logical] = primary_codes[0]  # best guess
                logger.error(
                    f"FS220: '{logical}' column not found. "
                    f"Primary: {primary_codes}, Keywords: {keywords}. "
                    f"This quarter's data may be incomplete for this field."
                )

    return mapping


def _find_col_by_description(actual_cols: set, acct_desc: dict, keywords: tuple) -> str | None:
    """Search AcctDesc.txt for a column whose description matches keywords."""
    for col in actual_cols:
        desc = acct_desc.get(col, "").lower()
        if any(kw in desc for kw in keywords):
            return col
    return None


def parse_acct_desc(raw: str) -> dict:
    """
    Parse AcctDesc.txt → dict of {ACCT_CODE: description}.
    This ships in every NCUA ZIP and maps every column to plain English.
    """
    result = {}
    try:
        reader = csv.DictReader(io.StringIO(raw))
        for row in reader:
            # Column names vary: "Account_Code", "ACCT_CODE", "Code" etc.
            code = (row.get("Account_Code") or row.get("ACCT_CODE") or
                    row.get("Code") or row.get("ACCOUNT") or "").strip()
            desc = (row.get("Account_Description") or row.get("DESCRIPTION") or
                    row.get("Description") or row.get("DESC") or "").strip()
            if code and desc:
                result[code] = desc
    except Exception as e:
        logger.warning(f"Could not parse AcctDesc.txt: {e}")
    return result


def build_schema_map(foicu_rows: list, fs220_rows: list, acct_desc_raw: str, quarter: str) -> NCUASchemaMap:
    """
    Build a complete SchemaMap from actual file contents.
    Called once per quarterly download. Results logged for audit trail.
    """
    schema = NCUASchemaMap(quarter=quarter)
    acct_desc = parse_acct_desc(acct_desc_raw)
    logger.info(f"AcctDesc: {len(acct_desc)} account descriptions loaded")

    foicu_map = probe_foicu_schema(foicu_rows)
    fs220_map = probe_fs220_schema(fs220_rows, acct_desc)

    # Apply FOICU mappings
    schema.col_cu_number = foicu_map.get("cu_number", "CU_NUMBER")
    schema.col_cu_name   = foicu_map.get("cu_name", "CU_NAME")
    schema.col_city      = foicu_map.get("city", "CITY")
    schema.col_state     = foicu_map.get("state", "STATE")
    schema.col_zip       = foicu_map.get("zip", "ZIP_CODE")
    schema.col_cu_type   = foicu_map.get("cu_type", "CU_TYPE")
    schema.col_licu      = foicu_map.get("licu", "LIMITED_INC")
    schema.col_tom_code  = foicu_map.get("tom_code", "TOM_CODE")

    # Apply FS220 mappings
    schema.col_assets     = fs220_map.get("assets",     "ACCT_010")
    schema.col_loans      = fs220_map.get("loans",      "ACCT_025B")
    schema.col_shares     = fs220_map.get("shares",     "ACCT_657")
    schema.col_members    = fs220_map.get("members",    "ACCT_730")
    schema.col_net_worth  = fs220_map.get("net_worth",  "ACCT_940")
    schema.col_net_income = fs220_map.get("net_income", "ACCT_902")

    # Log the final mapping for audit trail
    logger.info(f"Schema map for {quarter}:")
    logger.info(f"  assets={schema.col_assets}, loans={schema.col_loans}, "
                f"shares={schema.col_shares}, members={schema.col_members}, "
                f"net_worth={schema.col_net_worth}")
    logger.info(f"  cu_name={schema.col_cu_name}, state={schema.col_state}, "
                f"licu={schema.col_licu}")

    return schema


def validate_schema(schema: NCUASchemaMap, foicu_rows: list, fs220_rows: list) -> list[str]:
    """
    Run sanity checks after schema detection.
    Returns list of warning strings (empty = all good).
    """
    warnings = []

    if not foicu_rows:
        warnings.append("FOICU.txt is empty")
    if not fs220_rows:
        warnings.append("FS220.txt is empty")
        return warnings

    # Check row counts match
    if abs(len(foicu_rows) - len(fs220_rows)) > 100:
        warnings.append(
            f"Row count mismatch: FOICU={len(foicu_rows)}, FS220={len(fs220_rows)}. "
            f"Expected similar numbers."
        )

    # Check assets column has reasonable values
    sample = fs220_rows[:100]
    def gi(r, col):
        try: return int(float(str(r.get(col,"0") or "0").replace(",","")))
        except: return 0

    assets_values = [gi(r, schema.col_assets) for r in sample]
    nonzero = sum(1 for v in assets_values if v > 0)
    if nonzero < 10:
        warnings.append(
            f"Column '{schema.col_assets}' has only {nonzero}/100 non-zero values. "
            f"Assets column mapping may be wrong."
        )

    # Check total assets is plausible (should be in $trillions across all CUs)
    total_assets = sum(gi(r, schema.col_assets) for r in fs220_rows)
    if total_assets < 1_000_000_000:   # less than $1B total for all CUs = suspicious
        warnings.append(
            f"Total assets = ${total_assets:,} — suspiciously low. "
            f"Values may be in wrong unit or column is wrong."
        )
    elif total_assets > 10_000_000_000_000:  # more than $10T = suspicious
        warnings.append(
            f"Total assets = ${total_assets:,} — suspiciously high."
        )
    else:
        logger.info(f"Validation OK: total assets = ${total_assets/1e12:.2f}T across {len(fs220_rows)} CUs")

    return warnings
