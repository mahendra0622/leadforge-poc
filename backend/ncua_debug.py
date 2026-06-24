"""
Inspect FS220.txt financial columns and join key with FOICU.txt
    python ncua_debug.py
"""
import sys, os, io, csv, zipfile, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

URL = "https://ncua.gov/files/publications/analysis/call-report-data-2024-12.zip"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "*/*",
    "Referer": "https://ncua.gov/analysis/credit-union-corporate-call-report-data/quarterly-data",
}

print("Downloading NCUA Q4 2024 ZIP...")
req = urllib.request.Request(URL, headers=HEADERS)
with urllib.request.urlopen(req, timeout=120) as resp:
    data = resp.read()
print(f"Downloaded {len(data)/1e6:.1f} MB\n")

with zipfile.ZipFile(io.BytesIO(data)) as z:

    # ── FS220.txt — main financial table ──────────────────────
    print("=== FS220.txt — ALL COLUMNS + SAMPLE ROW ===")
    raw = z.read("FS220.txt").decode("utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(raw)))
    print(f"  Total rows: {len(rows)}")
    print(f"  Column count: {len(rows[0]) if rows else 0}")
    print(f"\n  All columns with sample values:")
    if rows:
        for i, (k, v) in enumerate(rows[0].items()):
            print(f"    [{i:03d}] {k:<25} = {str(v)[:50]}")

    # ── FOICU.txt — directory: name, state, address ───────────
    print("\n\n=== FOICU.txt — ALL COLUMNS ===")
    raw2 = z.read("FOICU.txt").decode("utf-8", errors="replace")
    foicu_rows = list(csv.DictReader(io.StringIO(raw2)))
    print(f"  Total rows: {len(foicu_rows)}")
    print(f"  All columns:")
    if foicu_rows:
        for i, k in enumerate(foicu_rows[0].keys()):
            print(f"    [{i:03d}] {k:<25} = {str(foicu_rows[0][k])[:50]}")
