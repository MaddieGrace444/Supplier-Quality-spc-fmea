"""
Supplier Quality Monitoring: Fabless Semiconductor Case Study
=============================================================

Scenario
--------
"NovaChip" is a fabless chip company. It designs chips but sends production
to an outside foundry ("Foundry A"). As the supplier quality engineer, you
watch the foundry's data to catch problems before bad chips reach customers.

This script does three things:
  1. X-bar and R control chart on a key wafer measurement (gate oxide
     thickness), with Western Electric rule checks to spot a process shift.
  2. Pareto chart of customer return failures, to find the "vital few"
     defect types driving most problems.
  3. An FMEA (Failure Mode and Effects Analysis) workbook in Excel, with
     RPN calculated by formula and risks ranked.

All data is simulated. Run:  python quality_analysis.py
Outputs land in ./output/
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

RNG = np.random.default_rng(42)  # fixed seed so results are repeatable

# Colors used across both charts
NAVY = "#1F3A5F"
RED = "#C0392B"
GRAY = "#7F8C8D"
GOLD = "#D68910"


# ---------------------------------------------------------------------------
# PART 1: X-bar and R control chart
# ---------------------------------------------------------------------------
# Each lot, the foundry measures gate oxide thickness on 5 wafers.
# Target is 20.0 angstroms. Starting at lot 19, a deposition tool drifts
# after maintenance and the oxide comes out thinner. Thin oxide is what
# breaks down under voltage stress, which links this chart to the #1
# failure on the Pareto. The chart should catch the shift.

N_LOTS = 30
SUBGROUP = 5          # wafers measured per lot
TARGET = 20.0         # angstroms
SIGMA = 0.15          # normal process variation
SHIFT_START = 19      # lot where the drift begins (1-indexed)
SHIFT_SIZE = -0.22    # how far the mean moves (negative = thinner oxide)
SPEC_LIMITS = (19.4, 20.6)  # customer spec: 20.0 +/- 0.6 Å (simulated)

# Control chart constants for subgroup size n=5 (from standard SPC tables)
A2, D3, D4 = 0.577, 0.0, 2.114

# Number of baseline lots used to set control limits (Phase I).
# Limits come from a period when the process was known to be stable,
# then later lots are judged against those limits (Phase II).
BASELINE_LOTS = 15


def simulate_lots() -> pd.DataFrame:
    rows = []
    for lot in range(1, N_LOTS + 1):
        mean = TARGET + (SHIFT_SIZE if lot >= SHIFT_START else 0.0)
        readings = RNG.normal(mean, SIGMA, SUBGROUP)
        rows.append({"lot": f"L{lot:02d}", "lot_num": lot,
                     **{f"wafer_{i + 1}": round(v, 3) for i, v in enumerate(readings)}})
    df = pd.DataFrame(rows)
    wafer_cols = [c for c in df.columns if c.startswith("wafer_")]
    df["xbar"] = df[wafer_cols].mean(axis=1)
    df["range"] = df[wafer_cols].max(axis=1) - df[wafer_cols].min(axis=1)
    return df


def control_limits(df: pd.DataFrame) -> dict:
    base = df[df["lot_num"] <= BASELINE_LOTS]
    xbarbar = base["xbar"].mean()   # grand mean, the centerline
    rbar = base["range"].mean()     # average range
    return {
        "xbar_cl": xbarbar,
        "xbar_ucl": xbarbar + A2 * rbar,
        "xbar_lcl": xbarbar - A2 * rbar,
        "r_cl": rbar,
        "r_ucl": D4 * rbar,
        "r_lcl": D3 * rbar,
    }


def western_electric(df: pd.DataFrame, lim: dict) -> pd.DataFrame:
    """Flag the classic Western Electric rules on the X-bar chart.

    Rule 1: one point beyond 3 sigma (outside the control limits)
    Rule 2: 2 of 3 consecutive points beyond 2 sigma on the same side
    Rule 4: 8 consecutive points on the same side of the centerline
    (Rule 3, 4 of 5 beyond 1 sigma, is left as a practice exercise.)
    """
    cl = lim["xbar_cl"]
    sigma_x = (lim["xbar_ucl"] - cl) / 3
    x = df["xbar"].to_numpy()
    flags = [[] for _ in x]

    for i, v in enumerate(x):
        if v > lim["xbar_ucl"] or v < lim["xbar_lcl"]:
            flags[i].append("R1")

    for i in range(2, len(x)):
        window = x[i - 2:i + 1]
        if (window > cl + 2 * sigma_x).sum() >= 2 or (window < cl - 2 * sigma_x).sum() >= 2:
            flags[i].append("R2")

    for i in range(7, len(x)):
        window = x[i - 7:i + 1]
        if (window > cl).all() or (window < cl).all():
            flags[i].append("R4")

    df = df.copy()
    df["violations"] = [",".join(f) for f in flags]
    return df


def plot_control_chart(df: pd.DataFrame, lim: dict) -> Path:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True,
                                   gridspec_kw={"height_ratios": [3, 2]})
    x = df["lot_num"]

    # X-bar chart
    ax1.plot(x, df["xbar"], marker="o", color=NAVY, lw=1.5, ms=5, zorder=3)
    ax1.axhline(lim["xbar_ucl"], color=RED, ls="--", lw=1)
    ax1.axhline(lim["xbar_cl"], color=GRAY, lw=1)
    ax1.axhline(lim["xbar_lcl"], color=RED, ls="--", lw=1)
    flagged = df[df["violations"] != ""]
    ax1.scatter(flagged["lot_num"], flagged["xbar"], s=110, facecolors="none",
                edgecolors=RED, lw=2, zorder=4, label="Rule violation")
    first = flagged.iloc[0] if not flagged.empty else None
    if first is not None:
        below = first["xbar"] < lim["xbar_cl"]
        text_y = lim["xbar_lcl"] - 0.12 if below else lim["xbar_ucl"] + 0.08
        ax1.annotate(f"First signal: lot {first['lot']}\n({first['violations']})",
                     xy=(first["lot_num"], first["xbar"]),
                     xytext=(first["lot_num"] - 9, text_y),
                     arrowprops=dict(arrowstyle="->", color=RED), color=RED, fontsize=9)
    ax1.axvspan(0.5, BASELINE_LOTS + 0.5, color=NAVY, alpha=0.05)
    ax1.text(1, lim["xbar_lcl"] - 0.04, "Baseline lots used to set limits",
             fontsize=8, color=GRAY, va="top")
    for key, label in [("xbar_ucl", "UCL"), ("xbar_cl", "CL"), ("xbar_lcl", "LCL")]:
        ax1.text(N_LOTS + 0.7, lim[key], f"{label} {lim[key]:.3f}", va="center", fontsize=8,
                 color=GRAY)
    ax1.set_ylabel("Lot mean thickness (Å)")
    ax1.set_title("X-bar Chart: Gate Oxide Thickness, Foundry A", loc="left",
                  fontsize=12, fontweight="bold")
    ax1.legend(loc="upper right", bbox_to_anchor=(1.0, 0.93), frameon=False, fontsize=9)

    # R chart
    ax2.plot(x, df["range"], marker="o", color=NAVY, lw=1.5, ms=5)
    r_out = df[(df["range"] > lim["r_ucl"]) | (df["range"] < lim["r_lcl"])]
    ax2.scatter(r_out["lot_num"], r_out["range"], s=110, facecolors="none",
                edgecolors=RED, lw=2, zorder=4)
    ax2.axhline(lim["r_ucl"], color=RED, ls="--", lw=1)
    ax2.axhline(lim["r_cl"], color=GRAY, lw=1)
    ax2.axhline(lim["r_lcl"], color=RED, ls="--", lw=1)
    for key, label in [("r_ucl", "UCL"), ("r_cl", "CL")]:
        ax2.text(N_LOTS + 0.7, lim[key], f"{label} {lim[key]:.3f}", va="center", fontsize=8,
                 color=GRAY)
    ax2.set_ylabel("Lot range (Å)")
    ax2.set_xlabel("Lot number")
    ax2.set_title("R Chart: Within-Lot Spread", loc="left", fontsize=11, fontweight="bold")
    ax2.set_xticks(range(1, N_LOTS + 1, 2))

    for ax in (ax1, ax2):
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_xlim(0.5, N_LOTS + 0.5)

    fig.tight_layout()
    path = OUT / "control_chart.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# PART 2: Pareto chart of customer returns
# ---------------------------------------------------------------------------
# Failure analysis results on chips customers sent back last quarter.

RETURNS = {
    "Gate oxide breakdown": 48,
    "Wire bond lift": 31,
    "Package crack": 14,
    "Metal short": 9,
    "ESD damage": 7,
    "Solder void": 5,
    "Mislabel / wrong part": 3,
    "Other": 3,
}


def plot_pareto() -> tuple[Path, pd.DataFrame]:
    s = pd.Series(RETURNS).sort_values(ascending=False)
    # "Other" always goes last on a Pareto, even if it isn't smallest
    s = pd.concat([s.drop("Other"), s[["Other"]]])
    cum_pct = s.cumsum() / s.sum() * 100

    fig, ax = plt.subplots(figsize=(11, 5.5))
    colors = [NAVY if c <= 80 or i == 0 else "#A9B7C6"
              for i, c in enumerate(cum_pct.shift(fill_value=0))]
    bars = ax.bar(s.index, s.values, color=colors)
    ax.bar_label(bars, fontsize=9, label_type="center", color="white", fontweight="bold")
    ax.set_ylabel("Returned units")
    ax.tick_params(axis="x", rotation=25)
    plt.setp(ax.get_xticklabels(), ha="right")

    ax2 = ax.twinx()
    ax2.plot(s.index, cum_pct.values, color=GOLD, marker="o", lw=2)
    ax2.axhline(80, color=GOLD, ls=":", lw=1)
    ax2.text(len(s) - 0.6, 81.5, "80% line", color=GOLD, fontsize=8, ha="right")
    ax2.set_ylim(0, 105)
    ax2.set_ylabel("Cumulative %")
    for i, v in enumerate(cum_pct.values):
        ax2.text(i + 0.12, v - 6, f"{v:.0f}%", ha="left", fontsize=8, color=GOLD)

    top = cum_pct[cum_pct.shift(fill_value=0) < 80]
    ax.set_title(f"Pareto: Customer Returns by Failure Mode (n={s.sum()})\n"
                 f"{len(top)} of {len(s)} categories drive {top.iloc[-1]:.0f}% of returns",
                 loc="left", fontsize=12, fontweight="bold")
    for a in (ax, ax2):
        a.spines[["top"]].set_visible(False)

    fig.tight_layout()
    path = OUT / "pareto_chart.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)

    table = pd.DataFrame({"failure_mode": s.index, "count": s.values,
                          "cumulative_pct": cum_pct.round(1).values})
    return path, table


# ---------------------------------------------------------------------------
# PART 3: FMEA workbook
# ---------------------------------------------------------------------------
# Process FMEA for the supplier side of NovaChip's product flow.
# Ratings use the common 1-10 scales (see the "Rating Scales" tab).
# RPN = Severity x Occurrence x Detection, written as an Excel formula.

FMEA_ROWS = [
    # step, function, failure mode, effect, S, cause, O, current control, D, action, owner
    ("Wafer fab: gate oxide deposition", "Grow oxide layer to 20 Å target",
     "Oxide too thick", "Higher threshold voltage; chip runs slow or fails speed test",
     8, "Deposition tool drift after maintenance", 5,
     "Foundry inline thickness measurement, 5 wafers/lot", 4,
     "Require foundry to share SPC data weekly; add Western Electric rule alerts",
     "Supplier Quality"),
    ("Wafer fab: gate oxide deposition", "Grow oxide layer to 20 Å target",
     "Oxide too thin / pinholes", "Gate oxide breakdown in the field; customer return",
     9, "Particle contamination in chamber", 4,
     "Final electrical test at foundry", 5,
     "Add burn-in screen for automotive lots; audit foundry chamber clean schedule",
     "Supplier Quality"),
    ("Wafer fab: metallization", "Form metal interconnect lines",
     "Metal short between lines", "Chip dead on arrival; yield loss",
     7, "Lithography defect / under-etch", 3,
     "Foundry defect inspection, sampled", 4,
     "Request defect density trend in quarterly business review",
     "Supplier Quality"),
    ("Assembly (OSAT): wire bonding", "Connect die pads to package leads",
     "Wire bond lift", "Intermittent open circuit; field failure",
     8, "Bond pad contamination or low bond force", 5,
     "Pull test, 1 unit per shift", 6,
     "Increase pull test sampling; require 8D for any lift above 0.1%",
     "Supplier Quality"),
    ("Assembly (OSAT): molding", "Encapsulate die in package",
     "Package crack", "Moisture enters; corrosion over time",
     7, "Mold compound cure profile out of spec", 3,
     "Visual inspection plus X-ray sampling", 4,
     "Add acoustic microscopy (C-SAM) sampling per lot",
     "Supplier Quality"),
    ("Final test", "Screen out bad parts before shipping",
     "Test escape (bad part passes)", "Defective chip reaches customer",
     9, "Test program gap; limits set too wide", 3,
     "Test program review at release", 5,
     "Correlate field returns back to test data; tighten limits",
     "Test Engineering"),
    ("Handling and shipping", "Ship correct parts without damage",
     "ESD damage", "Latent damage, early field failure",
     6, "Ungrounded handling at pack station", 3,
     "ESD audit, annual", 5,
     "Move ESD audits to quarterly; add wrist strap logging",
     "Supplier Quality"),
    ("Handling and shipping", "Ship correct parts without damage",
     "Mislabel / wrong part", "Customer builds with wrong chip; line down",
     8, "Manual label entry", 2,
     "Barcode scan at pack-out", 3,
     "None required; monitor", "Logistics"),
]

HEADERS = ["#", "Process Step", "Function", "Potential Failure Mode",
           "Potential Effect", "Severity (S)", "Potential Cause", "Occurrence (O)",
           "Current Control", "Detection (D)", "RPN (S×O×D)", "Priority",
           "Recommended Action", "Owner"]
WIDTHS = [5, 26, 26, 24, 34, 10, 30, 12, 30, 11, 12, 11, 42, 16]

FONT = "Arial"
HEADER_FILL = PatternFill("solid", start_color="1F3A5F")
INPUT_FONT = Font(name=FONT, size=10, color="0000FF")   # blue = rating you can edit
BODY_FONT = Font(name=FONT, size=10)
THIN = Side(style="thin", color="BFC5CC")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="top")

# Action threshold: many teams act on RPN >= 100, or on any Severity >= 9.
RPN_THRESHOLD = 100


def build_fmea() -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "FMEA"

    ws["A1"] = "Process FMEA: Supplier Quality, Fabless Chip (NovaChip / Foundry A / OSAT)"
    ws["A1"].font = Font(name=FONT, size=14, bold=True, color="1F3A5F")
    ws["A2"] = ("Blue numbers are ratings you can change (1 to 10). RPN and Priority "
                "recalculate automatically. Scales are on the 'Rating Scales' tab.")
    ws["A2"].font = Font(name=FONT, size=9, italic=True, color="555555")
    ws["A3"] = "RPN action threshold:"
    ws["A3"].font = Font(name=FONT, size=10, bold=True)
    ws["E3"] = RPN_THRESHOLD
    ws["E3"].font = Font(name=FONT, size=10, bold=True, color="0000FF")
    ws["E3"].fill = PatternFill("solid", start_color="FFFF00")
    ws["E3"].comment = Comment(
        "Assumption: act on RPN >= 100 or Severity >= 9. Common industry rule of thumb; "
        "AIAG-VDA (2019) now prefers Action Priority tables, but RPN is still widely used.",
        "Madison")
    ws.merge_cells("A3:D3")

    header_row = 5
    for col, (h, w) in enumerate(zip(HEADERS, WIDTHS), start=1):
        c = ws.cell(row=header_row, column=col, value=h)
        c.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
        c.fill = HEADER_FILL
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = BORDER
        ws.column_dimensions[get_column_letter(col)].width = w
    ws.row_dimensions[header_row].height = 32

    first = header_row + 1
    for i, row in enumerate(FMEA_ROWS):
        r = first + i
        step, func, mode, effect, s, cause, o, control, d, action, owner = row
        values = [i + 1, step, func, mode, effect, s, cause, o, control, d,
                  f"=F{r}*H{r}*J{r}",
                  f'=IF(OR(K{r}>=$E$3,F{r}>=9),"ACT","Monitor")',
                  action, owner]
        for col, v in enumerate(values, start=1):
            c = ws.cell(row=r, column=col, value=v)
            c.border = BORDER
            c.font = INPUT_FONT if col in (6, 8, 10) else BODY_FONT
            c.alignment = CENTER if col in (1, 6, 8, 10, 11, 12) else WRAP
        ws.row_dimensions[r].height = 48
    last = first + len(FMEA_ROWS) - 1

    # Highlight high-risk rows
    red_fill = PatternFill("solid", start_color="F5B7B1")
    amber_fill = PatternFill("solid", start_color="FCE4B6")
    ws.conditional_formatting.add(f"K{first}:K{last}",
                                  CellIsRule(operator="greaterThanOrEqual",
                                             formula=["$E$3"], fill=red_fill))
    ws.conditional_formatting.add(f"L{first}:L{last}",
                                  CellIsRule(operator="equal", formula=['"ACT"'],
                                             fill=amber_fill))

    # Summary block
    srow = last + 2
    summary = [
        ("Failure modes analyzed", f"=COUNTA(D{first}:D{last})"),
        ("Highest RPN", f"=MAX(K{first}:K{last})"),
        ("Highest-risk failure mode",
         f"=INDEX(D{first}:D{last},MATCH(MAX(K{first}:K{last}),K{first}:K{last},0))"),
        ("Items flagged ACT", f'=COUNTIF(L{first}:L{last},"ACT")'),
        ("Average RPN", f"=ROUND(AVERAGE(K{first}:K{last}),0)"),
    ]
    ws.cell(row=srow, column=2, value="Summary").font = Font(name=FONT, size=11, bold=True)
    for j, (label, formula) in enumerate(summary, start=1):
        ws.cell(row=srow + j, column=2, value=label).font = BODY_FONT
        c = ws.cell(row=srow + j, column=3, value=formula)
        c.font = Font(name=FONT, size=10, bold=True)

    ws.freeze_panes = ws.cell(row=first, column=3)

    # Rating scales tab
    sc = wb.create_sheet("Rating Scales")
    sc["A1"] = "FMEA Rating Scales (simplified, based on AIAG conventions)"
    sc["A1"].font = Font(name=FONT, size=13, bold=True, color="1F3A5F")
    scale_rows = [
        ("Rating", "Severity: how bad is the effect?", "Occurrence: how often does the cause happen?",
         "Detection: how likely are we to MISS it?"),
        (10, "Safety risk, no warning", "Almost certain (≥ 1 in 10)", "No control can detect it"),
        (9, "Safety or regulatory risk, with warning", "Very high", "Very remote chance of detection"),
        (8, "Product inoperable, total loss of function", "High (about 1 in 20)", "Remote"),
        (7, "Major loss of performance", "High", "Very low"),
        (6, "Partial loss of function", "Moderate (about 1 in 100)", "Low"),
        (5, "Reduced performance, customer notices", "Moderate", "Moderate"),
        (4, "Minor defect, most customers notice", "Moderately low", "Moderately high"),
        (3, "Minor defect, some customers notice", "Low (about 1 in 10,000)", "High"),
        (2, "Very minor, discerning customers notice", "Very low", "Very high"),
        (1, "No effect", "Remote, failure eliminated", "Almost certain to detect"),
    ]
    for i, row in enumerate(scale_rows, start=3):
        for j, v in enumerate(row, start=1):
            c = sc.cell(row=i, column=j, value=v)
            c.border = BORDER
            c.alignment = Alignment(wrap_text=True, vertical="top",
                                    horizontal="center" if j == 1 else "left")
            if i == 3:
                c.font = Font(name=FONT, size=10, bold=True, color="FFFFFF")
                c.fill = HEADER_FILL
            else:
                c.font = BODY_FONT
    for col, w in zip("ABCD", [8, 40, 40, 40]):
        sc.column_dimensions[col].width = w
    sc["A15"] = ("Note: Detection is scored backwards from what people expect. "
                 "A HIGH number means the problem is HARD to catch.")
    sc["A15"].font = Font(name=FONT, size=9, italic=True, color="555555")

    path = OUT / "fmea_supplier_quality.xlsx"
    wb.save(path)
    return path


# ---------------------------------------------------------------------------
# Run everything
# ---------------------------------------------------------------------------

def main() -> None:
    df = simulate_lots()
    lim = control_limits(df)
    df = western_electric(df, lim)
    df.round(4).to_csv(OUT / "lot_data.csv", index=False)
    cc_path = plot_control_chart(df, lim)

    pareto_path, pareto_table = plot_pareto()
    fmea_path = build_fmea()

    flagged = df[df["violations"] != ""]
    r_out = df[df["range"] > lim["r_ucl"]]
    print("=== Control chart ===")
    print(f"Centerline {lim['xbar_cl']:.3f} Å | UCL {lim['xbar_ucl']:.3f} | "
          f"LCL {lim['xbar_lcl']:.3f}")
    if flagged.empty:
        print("No rule violations. Process in control.")
    else:
        print(f"First signal at lot {flagged.iloc[0]['lot']} "
              f"(drift was injected at lot L{SHIFT_START:02d})")
        print(flagged[["lot", "xbar", "violations"]].to_string(index=False))

    for _, row in r_out.iterrows():
        print(f"R chart signal: lot {row['lot']} range {row['range']:.3f} > UCL {lim['r_ucl']:.3f}")

    print("\n=== Pareto ===")
    print(pareto_table.to_string(index=False))

    print(f"\nSaved: {cc_path.name}, {pareto_path.name}, {fmea_path.name}, lot_data.csv")


if __name__ == "__main__":
    main()
