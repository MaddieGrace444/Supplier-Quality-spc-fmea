# Supplier Quality Monitoring: Fabless Semiconductor Case Study

A small quality engineering project built in Python. It plays the role of a supplier quality engineer at a fabless chip company ("NovaChip") watching data from an outside foundry and assembly house. All data is simulated.

![Control chart](output/control_chart.png)

## What's in it

| Output | Quality tool | What it shows |
|---|---|---|
| `control_chart.png` | X-bar and R chart (SPC) | A deposition tool drifts at lot 19. Western Electric rules catch it on the first affected lot. |
| `pareto_chart.png` | Pareto analysis | 4 of 8 failure types drive 85% of customer returns. Gate oxide breakdown is #1. |
| `fmea_supplier_quality.xlsx` | Process FMEA | 8 failure modes across fab, assembly, test, and shipping, scored for Severity, Occurrence, and Detection. RPN and priority are live Excel formulas. |
| `lot_data.csv` | Raw data | 30 lots x 5 wafers of thickness measurements with rule violations flagged. |

## How the pieces connect

1. **Pareto** says gate oxide breakdown is the biggest source of customer returns.
2. **Control chart** shows gate oxide thickness drifting out of control starting at lot 19.
3. **FMEA** ranks the oxide failure modes as high priority (RPN 160 and 180) and lists actions: weekly SPC data sharing from the foundry, rule-based alerts, and a burn-in screen for automotive lots.
4. Next step in a real job: open an **8D** with the foundry, using **5-Why** to find why the tool drifted after maintenance.

## Methods

- **Control limits** come from the first 15 lots (Phase I baseline), then later lots are judged against them (Phase II). Constants for subgroup size 5: A2 = 0.577, D3 = 0, D4 = 2.114.
- **Western Electric rules checked:** Rule 1 (point beyond 3 sigma), Rule 2 (2 of 3 beyond 2 sigma), Rule 4 (8 in a row on one side). Rule 3 is left as an exercise.
- **FMEA scales** follow simplified AIAG conventions (1 to 10). Action threshold is RPN 100 or higher, or any Severity of 9 or higher. Note that the 2019 AIAG-VDA handbook moved to Action Priority tables; RPN is used here because it's still common and easy to read.

## Run it

```bash
pip install -r requirements.txt
python quality_analysis.py
```

## Skills shown

Statistical process control, root cause thinking, risk prioritization, supplier quality concepts (foundry and OSAT), ISO 9001 / IATF 16949 style documentation, Python data analysis.
