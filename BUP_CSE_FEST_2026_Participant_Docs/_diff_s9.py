"""Dump Sample 09 both expected and your computed side by side."""
import json, urllib.request

URL = "http://127.0.0.1:8000/optimize-energy"

with open(r"c:\Users\Sabab\Documents\cd\Team-Random\BUP_CSE_FEST_2026_Participant_Docs\tests\public_cases.json", "r", encoding="utf-8") as f:
    pack = json.load(f)

c = pack["cases"][8]
inp = c["input"]
out = json.loads(urllib.request.urlopen(urllib.request.Request(
    URL, data=json.dumps(inp).encode("utf-8"),
    headers={"Content-Type": "application/json"}), timeout=60).read())

print(f"{'h':>3} {'YouG':>8} {'RefG':>8} {'YouS':>8} {'RefS':>8} {'YouAct':>10} {'RefAct':>10} {'YouBk':>8} {'RefBk':>8} {'YouEaft':>8} {'RefEaft':>8}")
for yp, ep in zip(out["hourly_plan"], c["expected_output"]["hourly_plan"]):
    print(f"{yp['hour']:>3} {yp['grid_kwh']:>8.2f} {ep['grid_kwh']:>8.2f} {yp['solar_used_kwh']:>8.2f} {ep['solar_used_kwh']:>8.2f} {yp['battery_action']:>10} {ep['battery_action']:>10} {yp['battery_kwh']:>8.2f} {ep['battery_kwh']:>8.2f} {yp['battery_energy_after_kwh']:>8.2f} {ep['battery_energy_after_kwh']:>8.2f}")
print(f"\nYour total: {out['total_cost_bdt']}  Ref: {c['expected_output']['total_cost_bdt']}")
