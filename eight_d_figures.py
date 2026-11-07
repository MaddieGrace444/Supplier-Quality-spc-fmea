"""
Figures for the 8D report (8D_Report.md)
========================================

Builds two charts that support the 8D investigation into thin gate oxide:

  1. fishbone_diagram.png   Ishikawa (cause and effect) diagram used in D4.
                            Shows every suspected cause the team brainstormed,
                            which ones the data ruled out, and which were
                            confirmed as root causes.
  2. verification_chart.png X-bar chart for lots 1 to 45 used in D6.
                            Lots 31 to 45 are made AFTER the fix, to prove the
                            process went back to normal. Also calculates Cpk
                            (process capability) before, during, and after.

Reuses the simulated data and control limits from quality_analysis.py, so the
numbers match the rest of the project. All data is simulated.

Run:  python eight_d_figures.py
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import quality_analysis as qa

D2 = 2.326            # SPC table constant for subgroup size 5 (sigma = Rbar / d2)
FIX_LOTS = 15         # lots made after the corrective action
VERIFY_SEED = 21      # separate random seed for the post-fix lots
LSL, USL = qa.SPEC_LIMITS


# ---------------------------------------------------------------------------
# Data: original 30 lots + 15 lots after the fix
# ---------------------------------------------------------------------------

def build_full_history() -> tuple[pd.DataFrame, dict]:
    df = qa.simulate_lots()                # lots 1 to 30, same as main project
    lim = qa.control_limits(df)

    rng = np.random.default_rng(VERIFY_SEED)
    rows = []
    for lot in range(qa.N_LOTS + 1, qa.N_LOTS + FIX_LOTS + 1):
        readings = rng.normal(qa.TARGET, qa.SIGMA, qa.SUBGROUP)  # back on target
        rows.append({"lot": f"L{lot:02d}", "lot_num": lot,
                     **{f"wafer_{i + 1}": round(v, 3) for i, v in enumerate(readings)}})
    post = pd.DataFrame(rows)
    wafer_cols = [c for c in post.columns if c.startswith("wafer_")]
    post["xbar"] = post[wafer_cols].mean(axis=1)
    post["range"] = post[wafer_cols].max(axis=1) - post[wafer_cols].min(axis=1)

    # Run rules restart after a confirmed process change, so a window of
    # "8 in a row" can't straddle the old problem lots and the new ones.
    # The control limits stay the same (from the original baseline).
    full = pd.concat([qa.western_electric(df, lim), qa.western_electric(post, lim)],
                     ignore_index=True)
    return full, lim


def cpk(group: pd.DataFrame) -> dict:
    """Process capability: how well the process fits inside the spec limits.

    sigma is estimated from the average range (Rbar / d2), the standard
    short-term method for X-bar and R charts.
    Cp  = spec width / process width          (ignores centering)
    Cpk = distance to nearest spec / 3 sigma  (penalizes being off center)
    """
    mean = group["xbar"].mean()
    sigma = group["range"].mean() / D2
    return {
        "mean": mean,
        "sigma": sigma,
        "cp": (USL - LSL) / (6 * sigma),
        "cpk": min(USL - mean, mean - LSL) / (3 * sigma),
    }


# ---------------------------------------------------------------------------
# Figure 1: Verification chart
# ---------------------------------------------------------------------------

def plot_verification(full: pd.DataFrame, lim: dict, caps: dict) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    x = full["lot_num"]
    last = int(x.max())

    ax.axvspan(qa.SHIFT_START - 0.5, qa.N_LOTS + 0.5, color=qa.RED, alpha=0.06)
    ax.axvspan(qa.N_LOTS + 0.5, last + 0.5, color="#1E8449", alpha=0.06)
    ax.axvline(qa.N_LOTS + 0.5, color="#1E8449", lw=1.5)

    ax.plot(x, full["xbar"], marker="o", color=qa.NAVY, lw=1.5, ms=5, zorder=3)
    flagged = full[full["violations"] != ""]
    ax.scatter(flagged["lot_num"], flagged["xbar"], s=100, facecolors="none",
               edgecolors=qa.RED, lw=2, zorder=4, label="Control rule violation")

    ax.axhline(lim["xbar_ucl"], color=qa.RED, ls="--", lw=1)
    ax.axhline(lim["xbar_cl"], color=qa.GRAY, lw=1)
    ax.axhline(lim["xbar_lcl"], color=qa.RED, ls="--", lw=1)
    ax.axhline(USL, color=qa.GOLD, ls=":", lw=1.5)
    ax.axhline(LSL, color=qa.GOLD, ls=":", lw=1.5)

    for y, label, color in [(lim["xbar_ucl"], "UCL", qa.GRAY), (lim["xbar_cl"], "CL", qa.GRAY),
                            (lim["xbar_lcl"], "LCL", qa.GRAY), (USL, "USL (spec)", qa.GOLD),
                            (LSL, "LSL (spec)", qa.GOLD)]:
        ax.text(last + 0.8, y, f"{label} {y:.2f}", va="center", fontsize=8, color=color)

    band_y = USL - 0.04
    ax.text(8, band_y, "Before: normal", ha="center", va="top", fontsize=9, color=qa.GRAY)
    ax.text((qa.SHIFT_START + qa.N_LOTS) / 2, band_y,
            "Problem: thin oxide\n(lots placed on hold)", ha="center", va="top",
            fontsize=9, color=qa.RED)
    ax.text((qa.N_LOTS + last) / 2 + 0.5, band_y,
            "After fix: MFC recalibrated,\npost-PM qualification added", ha="center",
            va="top", fontsize=9, color="#1E8449")

    cap_text = "   |   ".join(
        f"{name}: Cpk {c['cpk']:.2f}" for name, c in caps.items())
    ax.text(0.5, -0.13, f"Process capability (target Cpk 1.33 or higher)   {cap_text}",
            transform=ax.transAxes, ha="center", fontsize=9, color=qa.NAVY,
            fontweight="bold")

    ax.set_ylim(LSL - 0.08, USL + 0.08)
    ax.set_xlim(0.5, last + 0.5)
    ax.set_xticks(range(1, last + 1, 2))
    ax.set_xlabel("Lot number")
    ax.set_ylabel("Lot mean thickness (Å)")
    ax.set_title("D6 Verification: Gate Oxide Thickness Before, During, and After the Fix",
                 loc="left", fontsize=12, fontweight="bold")
    ax.legend(loc="lower left", frameon=False, fontsize=9)
    ax.spines[["top", "right"]].set_visible(False)

    fig.tight_layout()
    fig.savefig(qa.OUT / "verification_chart.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Figure 2: Fishbone (Ishikawa) diagram
# ---------------------------------------------------------------------------
# status: "root" = confirmed root cause, "escape" = why it wasn't caught,
#         "ruled_out" = checked with data and eliminated

FISHBONE = {
    "Machine": [
        ("Gas flow controller (MFC)\nreplaced in PM, not recalibrated", "root"),
        ("Chamber not seasoned\nafter PM", "ruled_out"),
    ],
    "Method": [
        ("No qualification run\nbefore tool release", "root"),
        ("SPC rules turned off\nfor this parameter", "escape"),
    ],
    "Measurement": [
        ("Lots judged against spec\nlimits, not control limits", "escape"),
        ("Thickness gauge drift\n(gauge R&R passed)", "ruled_out"),
    ],
    "Material": [
        ("New precursor gas lot\n(same lot used before L19)", "ruled_out"),
        ("Wafer supplier change\n(none in period)", "ruled_out"),
    ],
    "People": [
        ("New technician on PM\n(followed checklist)", "ruled_out"),
        ("Monthly-only data review\nby NovaChip", "escape"),
    ],
    "Environment": [
        ("Fab temperature excursion\n(logs normal)", "ruled_out"),
        ("Humidity change\n(logs normal)", "ruled_out"),
    ],
}

STATUS_STYLE = {
    "root": dict(color=qa.RED, fontweight="bold"),
    "escape": dict(color=qa.GOLD, fontweight="bold"),
    "ruled_out": dict(color="#95A5A6", fontweight="normal"),
}


def plot_fishbone() -> None:
    fig, ax = plt.subplots(figsize=(14, 7.5))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")

    spine_y = 4.0
    head_x = 11.4
    ax.annotate("", xy=(head_x, spine_y), xytext=(0.6, spine_y),
                arrowprops=dict(arrowstyle="-|>", lw=3, color=qa.NAVY, mutation_scale=25))
    ax.text(head_x + 0.15, spine_y, "EFFECT\nGate oxide too thin\non lots L19 to L30\n"
            "(field breakdown)", va="center", ha="left", fontsize=11, fontweight="bold",
            color="white", bbox=dict(boxstyle="round,pad=0.6", fc=qa.NAVY, ec=qa.NAVY))

    cats = list(FISHBONE)
    top, bottom = cats[:3], cats[3:]
    bone_x = [2.6, 5.9, 9.2]   # where each bone meets the spine

    for row, sign in [(top, 1), (bottom, -1)]:
        for cat, bx in zip(row, bone_x):
            tip_x, tip_y = bx - 1.6, spine_y + sign * 3.1
            ax.plot([tip_x, bx], [tip_y, spine_y], color=qa.NAVY, lw=2)
            ax.text(tip_x, tip_y + sign * 0.25, cat, ha="center",
                    va="bottom" if sign > 0 else "top", fontsize=12,
                    fontweight="bold", color=qa.NAVY)
            for k, (cause, status) in enumerate(FISHBONE[cat]):
                frac = 0.33 + 0.38 * k           # position along the bone
                px = tip_x + (bx - tip_x) * frac
                py = tip_y + (spine_y - tip_y) * frac
                ax.plot([px - 1.25, px], [py, py], color="#BDC3C7", lw=1)
                ax.text(px - 1.3, py, cause, ha="right", va="center", fontsize=8.5,
                        **STATUS_STYLE[status])

    # legend
    lx, ly = 11.5, 1.4
    for i, (label, status) in enumerate([("Confirmed root cause (why it happened)", "root"),
                                         ("Escape cause (why it wasn't caught)", "escape"),
                                         ("Checked with data and ruled out", "ruled_out")]):
        ax.text(lx, ly - i * 0.4, "■ " + label, fontsize=9, **STATUS_STYLE[status])

    ax.set_title("D4 Root Cause Analysis: Fishbone (Ishikawa) Diagram", loc="left",
                 fontsize=13, fontweight="bold", color=qa.NAVY)
    fig.tight_layout()
    fig.savefig(qa.OUT / "fishbone_diagram.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------

def main() -> None:
    full, lim = build_full_history()
    groups = {
        "Before (L01-L18)": full[full["lot_num"] < qa.SHIFT_START],
        "Problem (L19-L30)": full[(full["lot_num"] >= qa.SHIFT_START)
                                  & (full["lot_num"] <= qa.N_LOTS)],
        "After fix (L31-L45)": full[full["lot_num"] > qa.N_LOTS],
    }
    caps = {name: cpk(g) for name, g in groups.items()}
    post_flags = groups["After fix (L31-L45)"]
    post_flags = post_flags[post_flags["violations"] != ""]

    plot_verification(full, lim, {k.split(" (")[0]: v for k, v in caps.items()})
    plot_fishbone()
    full.round(4).to_csv(qa.OUT / "lot_data_with_verification.csv", index=False)

    print("=== Process capability (spec 19.4 to 20.6 Å) ===")
    for name, c in caps.items():
        print(f"{name:22s} mean {c['mean']:.3f}  sigma {c['sigma']:.4f}  "
              f"Cp {c['cp']:.2f}  Cpk {c['cpk']:.2f}")
    print(f"\nRule violations after fix: {len(post_flags)}")
    if not post_flags.empty:
        print(post_flags[["lot", "xbar", "violations"]].to_string(index=False))
    problem = groups["Problem (L19-L30)"]
    print(f"\nProblem lots: min lot mean {problem['xbar'].min():.3f}, "
          f"lowest single wafer {problem.filter(like='wafer_').min().min():.3f}")
    print("Saved: verification_chart.png, fishbone_diagram.png, lot_data_with_verification.csv")


if __name__ == "__main__":
    main()
