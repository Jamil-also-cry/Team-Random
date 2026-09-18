"""Compare optimizer output vs sample expected_output for all 10 cases."""
import json
import urllib.request

URL = "http://127.0.0.1:8000/optimize-energy"

with open(r"c:\Users\Sabab\Documents\cd\Team-Random\BUP_CSE_FEST_2026_Participant_Docs\tests\public_cases.json", "r", encoding="utf-8") as f:
    pack = json.load(f)

print(f"{'ID':<11} {'YouCost':>10} {'RefCost':>10} {'Diff%':>7} {'YouPeak':>8} {'RefPeak':>8} {'YouGrid':>10} {'RefGrid':>10}")
for c in pack["cases"]:
    inp = c["input"]
    req = urllib.request.Request(
        URL,
        data=json.dumps(inp).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    out = json.loads(urllib.request.urlopen(req, timeout=60).read())
    exp = c["expected_output"]
    diff = (out["total_cost_bdt"] - exp["total_cost_bdt"]) / exp["total_cost_bdt"] * 100
    flag = " OK" if abs(out["total_cost_bdt"] - exp["total_cost_bdt"]) <= 0.01 * exp["total_cost_bdt"] + 0.01 else " MISMATCH"
    print(f"{c['id']:<11} {out['total_cost_bdt']:>10.2f} {exp['total_cost_bdt']:>10} {diff:>+6.2f}% {out['peak_grid_kwh']:>8.2f} {exp['peak_grid_kwh']:>8} {out['total_grid_kwh']:>10.2f} {exp['total_grid_kwh']:>10}  {flag}")
