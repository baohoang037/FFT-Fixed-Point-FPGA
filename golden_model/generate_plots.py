"""
================================================================================
 generate_plots.py
================================================================================
 Making 4 plot IEEE:
   1. sqnr_vs_bitwidth.png        -- SQNR vs word length (4 signal types)
   2. resource_utilization.png    -- LUT/FF/DSP/BRAM vs word length
   3. resource_tradeoff_real.png  -- SQNR vs combined hardware cost (trade-off)
   4. spectrum_comparison.png     -- Single-tone output spectrum (all bit-widths)

 how to run:
   cd FFT_project_NCKH/golden_model
   python generate_plots.py

 Output: ../plots/  

 Requirement:
   pip install numpy matplotlib
================================================================================
"""

import os
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")          
import matplotlib.pyplot as plt

# ── Output directory ──────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR   = os.path.dirname(SCRIPT_DIR)
TV_DIR     = os.path.join(ROOT_DIR, "test_vectors")
OUT_DIR    = os.path.join(ROOT_DIR, "plots")
os.makedirs(OUT_DIR, exist_ok=True)

# ── Verified numbers (from golden model + Vivado synthesis) ──────────────────
BIT_WIDTHS = [8, 10, 12, 14, 16]

SQNR_DATA = {
    "Single tone":        [10.15, 22.08, 34.39, 46.28, 58.35],
    "Multi tone":         [ 7.20, 19.78, 31.21, 43.53, 55.37],
    "Full-scale DC":      [15.33, 27.31, 39.36, 51.40, 63.44],
    "Random noise (avg)": [ 2.51, 14.46, 26.49, 38.52, 50.57],
}

UTIL = {
    "LUT":      [581, 829, 341, 366, 383],
    "FF":       [138, 146, 154, 162, 170],
    "BRAM":     [  2,   2,   2,   2,   2],
    "DSP48E1":  [  0,   0,   5,   5,   5],
}

MARKERS = ["o", "s", "^", "D"]
COLORS  = ["#1565C0", "#EF6C00", "#2E7D32", "#6A1B9A"]


# ════════════════════════════════════════════════════════════════════════════
# HELPER
# ════════════════════════════════════════════════════════════════════════════
def load_hex(path, W):
    """Load a $readmemh hex file and convert to float Q1.(W-1)."""
    vals = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            v = int(line, 16)
            if v >= (1 << (W - 1)):
                v -= (1 << W)
            vals.append(v / (1 << (W - 1)))
    return np.array(vals)


def get_spectrum_db(W):
    """Compute single-tone output magnitude spectrum (dBFS) from test vectors."""
    r_path = os.path.join(TV_DIR, f"tv_single_tone_bw{W}_real_hex.txt")
    i_path = os.path.join(TV_DIR, f"tv_single_tone_bw{W}_imag_hex.txt")
    if not os.path.exists(r_path):
        return None
    xr = load_hex(r_path, W)
    xi = load_hex(i_path, W)
    X  = np.fft.fft(xr + 1j * xi) / len(xr)
    return 20.0 * np.log10(np.abs(X[:len(xr) // 2]) + 1e-12)


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — SQNR vs Word Length
# ════════════════════════════════════════════════════════════════════════════
def plot_sqnr():
    fig, ax = plt.subplots(figsize=(7.5, 5.0))
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    for (label, vals), mk, col in zip(SQNR_DATA.items(), MARKERS, COLORS):
        ax.plot(BIT_WIDTHS, vals, marker=mk, color=col,
                lw=2.0, ms=8, label=label, zorder=3)
        for w, v in zip(BIT_WIDTHS, vals):
            ax.annotate(f"{v:.1f}",
                        (w, v), textcoords="offset points",
                        xytext=(0, 8), ha="center",
                        fontsize=7.5, color=col)

    # Theoretical input-only bound
    th = np.linspace(7.5, 16.5, 200)
    ax.plot(th, 6.02 * th + 1.76, "--", color="#888", lw=1.4,
            label="Input-only bound: 6.02W + 1.76 dB", zorder=1)

    # Quality zones
    ax.axhspan( 0,  30, color="#FFCDD2", alpha=0.22)
    ax.axhspan(30,  50, color="#FFF9C4", alpha=0.28)
    ax.axhspan(50, 110, color="#C8E6C9", alpha=0.22)
    ax.text(16.4,  15, "Low quality\n(<30 dB)",      ha="right", fontsize=7.5, color="#c62828")
    ax.text(16.4,  38, "Moderate quality\n(30–50 dB)", ha="right", fontsize=7.5, color="#e65100")
    ax.text(16.4,  55, "High quality\n(>50 dB)",      ha="right", fontsize=7.5, color="#1b5e20")

    ax.set_xlabel("Data word length W (bits)", fontsize=11)
    ax.set_ylabel("Output SQNR (dB)", fontsize=11)
    ax.set_title(
        "Output SQNR vs. Word Length\n"
        "Fixed-Point Radix-2 DIT FFT, N = 1024, Scaled Architecture",
        fontsize=11, fontweight="bold")
    ax.set_xticks(BIT_WIDTHS)
    ax.set_xlim(7.5, 16.5)
    ax.set_ylim(0, 105)
    ax.grid(True, ls="--", alpha=0.40)
    ax.legend(fontsize=8.5, loc="upper left",
              framealpha=0.95, edgecolor="#ccc")

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "sqnr_vs_bitwidth.png")
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  [1] Saved: {out}")


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — Resource Utilization (LUT/FF + DSP/BRAM)
# ════════════════════════════════════════════════════════════════════════════
def plot_utilization():
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.0))
    fig.patch.set_facecolor("white")

    x = np.arange(len(BIT_WIDTHS))
    w = 0.32
    labels_x = [f"{b}-bit" for b in BIT_WIDTHS]

    # ── Left: LUT & FF ──
    ax = axes[0]
    ax.set_facecolor("white")
    b1 = ax.bar(x - w / 2, UTIL["LUT"], w, label="LUT", color="#1565C0", zorder=3)
    b2 = ax.bar(x + w / 2, UTIL["FF"],  w, label="FF",  color="#43A047", zorder=3)
    for bar in list(b1) + list(b2):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 8,
                str(int(bar.get_height())),
                ha="center", va="bottom", fontsize=8.5, color="#222")
    ax.set_xticks(x); ax.set_xticklabels(labels_x)
    ax.set_xlabel("Data word length W (bits)", fontsize=10)
    ax.set_ylabel("Resource count", fontsize=10)
    ax.set_title("LUT and Flip-Flop Utilization\nvs. Word Length",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", ls="--", alpha=0.40)
    ax.set_ylim(0, max(UTIL["LUT"]) * 1.20)

    # ── Right: DSP & BRAM ──
    ax = axes[1]
    ax.set_facecolor("white")
    b3 = ax.bar(x - w / 2, UTIL["DSP48E1"], w,
                label="DSP48E1",       color="#E53935", zorder=3)
    b4 = ax.bar(x + w / 2, UTIL["BRAM"],    w,
                label="Block RAM tile", color="#FB8C00", zorder=3)
    for bar in list(b3) + list(b4):
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.08,
                str(int(bar.get_height())),
                ha="center", va="bottom", fontsize=8.5, color="#222")
    ax.set_xticks(x); ax.set_xticklabels(labels_x)
    ax.set_xlabel("Data word length W (bits)", fontsize=10)
    ax.set_ylabel("Resource count", fontsize=10)
    ax.set_title("DSP48E1 and Block RAM Utilization\nvs. Word Length",
                 fontsize=10, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(True, axis="y", ls="--", alpha=0.40)
    ax.set_ylim(0, max(UTIL["DSP48E1"]) * 1.55 + 1)

    # Crossover annotations
    ax.annotate("LUT-based multiplier\n(W < 12, DSP = 0)",
                xy=(0.28, 0.20), xycoords="axes fraction",
                fontsize=8.5, color="#B71C1C", ha="center",
                bbox=dict(boxstyle="round,pad=0.3",
                          fc="white", ec="#E53935", lw=1.2))
    ax.annotate("DSP48E1 inferred\n(W ≥ 12)",
                xy=(0.78, 0.60), xycoords="axes fraction",
                fontsize=8.5, color="#B71C1C", ha="center",
                bbox=dict(boxstyle="round,pad=0.3",
                          fc="white", ec="#E53935", lw=1.2))

    fig.suptitle(
        "Post-Synthesis Resource Utilization — "
        "Vivado 2018.3, Artix-7 xc7k70tfbv676-1",
        fontsize=11, fontweight="bold", y=1.02)
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "resource_utilization.png")
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  [2] Saved: {out}")


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — Trade-off Curve (SQNR vs combined cost)
# ════════════════════════════════════════════════════════════════════════════
def plot_tradeoff():
    sqnr_st = SQNR_DATA["Single tone"]
    cost    = [l + 100 * d for l, d in zip(UTIL["LUT"], UTIL["DSP48E1"])]

    fig, ax = plt.subplots(figsize=(8.5, 6.0))
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")

    sc = ax.scatter(cost, sqnr_st, s=220,
                    c=BIT_WIDTHS, cmap="plasma",
                    edgecolors="black", linewidth=1.2, zorder=5)

    # Labels for each point — offset left/right to avoid overlap
    offsets = {8: (-58, 8), 10: (-58, 8), 12: (16, 8), 14: (16, 8), 16: (16, 8)}
    for w, c_, s in zip(BIT_WIDTHS, cost, sqnr_st):
        ox, oy = offsets[w]
        ax.annotate(f"{w}-bit\n({s:.1f} dB)",
                    (c_, s), fontsize=9.5, va="center",
                    ha="right" if ox < 0 else "left",
                    xytext=(ox, oy), textcoords="offset points",
                    color="#222")

    # Knee point annotation — placed in the upper-left empty region
    knee_idx = BIT_WIDTHS.index(12)
    ax.annotate(
        "Knee point\n(W = 12 bit)\n34.4 dB SQNR",
        xy=(cost[knee_idx], sqnr_st[knee_idx]),
        xytext=(600, 48),          # upper-left area, well away from all dots
        fontsize=9.5, color="#C62828",
        arrowprops=dict(arrowstyle="-|>", color="#C62828", lw=1.8,
                        connectionstyle="arc3,rad=-0.25"),
        bbox=dict(boxstyle="round,pad=0.4", fc="white",
                  ec="#C62828", lw=1.5, alpha=0.95),
        zorder=6)

    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Word length W (bits)", fontsize=10)

    ax.set_xlabel("Combined hardware cost  (LUT + 100 \u00d7 DSP48E1)", fontsize=11)
    ax.set_ylabel("Output SQNR \u2014 single tone (dB)", fontsize=11)
    ax.set_title(
        "Accuracy vs. Hardware Cost Trade-off\n"
        "Fixed-Point FFT, N = 1024, Artix-7 xc7k70t",
        fontsize=12, fontweight="bold")
    ax.set_xlim(500, 1000)
    ax.set_ylim(0, 70)
    ax.grid(True, ls="--", alpha=0.40)

    fig.tight_layout()
    out = os.path.join(OUT_DIR, "resource_tradeoff_real.png")
    fig.savefig(out, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print(f"  [3] Saved: {out}")


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — Output Spectrum Comparison
# ════════════════════════════════════════════════════════════════════════════
def plot_spectrum():
    # Check test vectors are available
    r_path = os.path.join(TV_DIR, "tv_single_tone_bw8_real_hex.txt")
    if not os.path.exists(r_path):
        print("  [4] WARNING: test_vectors/ not found — run golden_model.py first.")
        print("      Skipping spectrum_comparison.png")
        return

    fig, axes = plt.subplots(len(BIT_WIDTHS), 1,
                             figsize=(9, 3.0 * len(BIT_WIDTHS)),
                             sharex=True)
    fig.patch.set_facecolor("white")

    col_cycle = ["#1565C0", "#EF6C00", "#2E7D32", "#6A1B9A", "#C62828"]

    ref_db = None
    for ax, W, col in zip(axes, BIT_WIDTHS, col_cycle):
        ax.set_facecolor("white")
        mag_db = get_spectrum_db(W)
        if mag_db is None:
            ax.text(0.5, 0.5, f"W={W}: hex file not found",
                    ha="center", transform=ax.transAxes)
            continue

        N2 = len(mag_db)
        fr = np.arange(N2)

        if ref_db is None:
            ref_db = mag_db.copy()   # treat first W=8 as baseline for comparison

        sqnr_val = SQNR_DATA["Single tone"][BIT_WIDTHS.index(W)]

        ax.plot(fr, mag_db, color=col, lw=0.85,
                label=f"W = {W} bit (fixed-point)", zorder=2)
        ax.set_ylabel("Magnitude (dBFS)", fontsize=9)
        ax.set_title(
            f"W = {W} bit  |  SQNR = {sqnr_val:.1f} dB  "
            f"|  Noise floor \u2248 {np.percentile(mag_db, 60):.0f} dBFS",
            fontsize=9.5, fontweight="bold")
        ax.set_ylim(-145, 5)
        ax.grid(True, ls="--", alpha=0.30)
        ax.legend(fontsize=8.5, loc="upper right")

    axes[-1].set_xlabel("Frequency bin index k  (0 to N/2\u22121)", fontsize=10)
    fig.suptitle(
        "Single-Tone Output Spectrum vs. Word Length\n"
        "N = 1024-point FFT  |  Input: single tone at bin 50",
        fontsize=12, fontweight="bold", y=1.003)
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "spectrum_comparison.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [4] Saved: {out}")


# ════════════════════════════════════════════════════════════════════════════
# FIGURE 5 — Quantization Noise Floor (one subplot per bit-width)
# ════════════════════════════════════════════════════════════════════════════
def plot_noise_floor():
    r_path = os.path.join(TV_DIR, "tv_single_tone_bw8_real_hex.txt")
    if not os.path.exists(r_path):
        print("  [5] WARNING: test_vectors/ not found — run golden_model.py first.")
        print("      Skipping noise_floor.png")
        return

    col_cycle  = ["#E53935", "#FB8C00", "#FDD835", "#43A047", "#1E88E5"]
    sqnr_vals  = SQNR_DATA["Single tone"]

    # Use W=16 as the closest-to-floating-point reference
    ref_db16 = get_spectrum_db(16)
    if ref_db16 is None:
        print("  [5] ERROR: W=16 test vector missing.")
        return

    N2 = len(ref_db16)
    fr = np.arange(N2)

    fig, axes = plt.subplots(len(BIT_WIDTHS), 1,
                             figsize=(10, 2.8 * len(BIT_WIDTHS)),
                             sharex=True)
    fig.patch.set_facecolor("white")

    for ax, W, col, sqnr in zip(axes, BIT_WIDTHS, col_cycle, sqnr_vals):
        ax.set_facecolor("white")
        mag_db = get_spectrum_db(W)
        if mag_db is None:
            ax.text(0.5, 0.5, f"W={W}: data not found",
                    ha="center", transform=ax.transAxes)
            continue

        err = mag_db - ref_db16

        # Mean noise floor — exclude signal bin region (45-55)
        mask = np.ones(N2, dtype=bool)
        mask[45:56] = False
        floor_mean = np.mean(err[mask])

        ax.fill_between(fr, err, alpha=0.20, color=col)
        ax.plot(fr, err, color=col, lw=0.85)
        ax.axhline(0,          color="#444", lw=0.9, ls="--", alpha=0.55,
                   label="W=16 reference (0 dB)")
        ax.axhline(floor_mean, color=col,   lw=1.3, ls=":",
                   label=f"Mean noise floor: {floor_mean:.1f} dB")

        ax.set_ylabel("Error (dB)", fontsize=9)
        ax.set_title(
            f"W = {W} bit  \u2502  SQNR = {sqnr:.1f} dB  "
            f"\u2502  Mean floor \u2248 {floor_mean:.1f} dB  (vs W=16 ref)",
            fontsize=9.5, fontweight="bold")
        ax.set_ylim(-55, 20)
        ax.grid(True, ls="--", alpha=0.28)
        ax.legend(fontsize=8.5, loc="upper right", framealpha=0.92)

    axes[-1].set_xlabel("Frequency bin index k  (0 to N/2\u22121)", fontsize=10)
    fig.suptitle(
        "Per-Bin Quantization Noise Floor vs. Word Length\n"
        "Error = fixed-point output \u2212 W=16 reference  "
        "|  Single tone at bin 50, N = 1024",
        fontsize=12, fontweight="bold", y=1.002)
    fig.tight_layout()
    out = os.path.join(OUT_DIR, "noise_floor.png")
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  [5] Saved: {out}")


# ════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 60)
    print("  Generating paper figures ...")
    print("=" * 60)
    plot_sqnr()
    plot_utilization()
    plot_tradeoff()
    plot_spectrum()
    plot_noise_floor()
    print("=" * 60)
    print(f"  All figures saved to: {OUT_DIR}")
    print("=" * 60)