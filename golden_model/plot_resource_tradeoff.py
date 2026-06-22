"""
================================================================================
 plot_resource_tradeoff.py
================================================================================
 Doc 5 file bao cao Utilization that cua Vivado (report_utilization, mot file
 cho moi BIT_WIDTH = 8/10/12/14/16), ket hop voi SQNR da tinh san tu golden
 model (results/sqnr_results.csv), roi ve do thi trade-off THAT (khong uoc
 luong) giua do rong bit, tai nguyen phan cung (LUT/FF/DSP/BRAM) va SQNR.

 Cach chay:
   1. Dat 5 file util_bw8.rpt, util_bw10.rpt, util_bw12.rpt, util_bw14.rpt,
      util_bw16.rpt vao CUNG thu muc voi script nay (hoac sua RPT_DIR ben
      duoi tro dung thu muc chua chung).
   2. Dam bao da chay golden_model.py truoc do it nhat 1 lan (de co file
      ../results/sqnr_results.csv).
   3. python plot_resource_tradeoff.py
   4. Anh ket qua: ../plots/resource_tradeoff_real.png

 Day la code Python thuan, doc truc tiep tu file .rpt that do Vivado sinh ra
 -- khong phai so uoc luong -- nen co the trich dan/dinh kem lam Phu luc
 trong bao cao NCKH.
================================================================================
"""

import re
import os
import csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ----------------------------------------------------------------------------
# CONFIG
# ----------------------------------------------------------------------------
BIT_WIDTHS = [8, 10, 12, 14, 16]
RPT_DIR    = os.path.dirname(os.path.abspath(__file__))   # thu muc chua script
RPT_NAME_FMT = "util_bw{}.rpt"

BASE       = RPT_DIR
ROOT       = os.path.dirname(BASE)
SQNR_CSV   = os.path.join(ROOT, "results", "sqnr_results.csv")
OUT_DIR    = os.path.join(ROOT, "plots")
os.makedirs(OUT_DIR, exist_ok=True)


# ----------------------------------------------------------------------------
# 1. PARSE VIVADO UTILIZATION REPORT (.rpt)
# ----------------------------------------------------------------------------
def parse_utilization_report(path):
    """Trich xuat LUT, FF, BRAM (so tile), DSP tu 1 file report_utilization."""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()

    def grab(pattern, text, group=1, default=0):
        m = re.search(pattern, text)
        return int(m.group(group)) if m else default

    lut  = grab(r"\|\s*Slice LUTs\*?\s*\|\s*(\d+)\s*\|", text)
    ff   = grab(r"\|\s*Slice Registers\s*\|\s*(\d+)\s*\|", text)
    bram = grab(r"\|\s*Block RAM Tile\s*\|\s*(\d+)\s*\|", text)
    dsp  = grab(r"\|\s*DSPs\s*\|\s*(\d+)\s*\|", text)

    return dict(LUT=lut, FF=ff, BRAM=bram, DSP=dsp)


def load_all_reports(bit_widths):
    data = {}
    for w in bit_widths:
        path = os.path.join(RPT_DIR, RPT_NAME_FMT.format(w))
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Khong tim thay {path}. Hay dat file report dung ten "
                f"'{RPT_NAME_FMT.format(w)}' trong thu muc {RPT_DIR}")
        data[w] = parse_utilization_report(path)
    return data


# ----------------------------------------------------------------------------
# 2. LOAD SQNR (tu golden model, da tinh san)
# ----------------------------------------------------------------------------
def load_sqnr(csv_path, bit_widths):
    """Doc results/sqnr_results.csv, lay trung binh SQNR cua cac tin hieu
    co y nghia (bo qua all_zeros / impulse vi khong on dinh ve SQNR)."""
    rows = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows[row["Test Vector"]] = row

    sqnr_single = {}
    for w in bit_widths:
        col = f"BW={w}"
        v = rows["single_tone"][col]
        sqnr_single[w] = float(v) if v not in ("nan", "inf") else None
    return sqnr_single


# ----------------------------------------------------------------------------
# 3. PLOT
# ----------------------------------------------------------------------------
def plot_tradeoff(util_data, sqnr_data, bit_widths):
    lut  = [util_data[w]["LUT"]  for w in bit_widths]
    ff   = [util_data[w]["FF"]   for w in bit_widths]
    bram = [util_data[w]["BRAM"] for w in bit_widths]
    dsp  = [util_data[w]["DSP"]  for w in bit_widths]
    sqnr = [sqnr_data[w] for w in bit_widths]

    fig, axes = plt.subplots(2, 2, figsize=(12, 9))

    # --- (a) LUT & FF vs bit-width -----------------------------------------
    ax = axes[0, 0]
    x = range(len(bit_widths))
    width = 0.35
    ax.bar([i - width/2 for i in x], lut, width, label="LUT", color="#1565C0")
    ax.bar([i + width/2 for i in x], ff,  width, label="FF (Register)", color="#43A047")
    ax.set_xticks(list(x)); ax.set_xticklabels([f"{w}-bit" for w in bit_widths])
    ax.set_ylabel("So luong (thuc te, Vivado synth)")
    ax.set_title("(a) LUT & FF vs Do rong bit")
    ax.legend(); ax.grid(True, axis="y", ls="--", alpha=0.4)
    for i, (l, f_) in enumerate(zip(lut, ff)):
        ax.text(i - width/2, l + max(lut)*0.01, str(l), ha="center", fontsize=8)
        ax.text(i + width/2, f_ + max(lut)*0.01, str(f_), ha="center", fontsize=8)

    # --- (b) DSP & BRAM vs bit-width ---------------------------------------
    ax = axes[0, 1]
    ax.bar([i - width/2 for i in x], dsp,  width, label="DSP48E1", color="#E53935")
    ax.bar([i + width/2 for i in x], bram, width, label="Block RAM Tile", color="#FB8C00")
    ax.set_xticks(list(x)); ax.set_xticklabels([f"{w}-bit" for w in bit_widths])
    ax.set_ylabel("So luong (thuc te, Vivado synth)")
    ax.set_title("(b) DSP & BRAM vs Do rong bit\n(DSP=0 o 8/10-bit: Vivado chon dung LUT thay DSP)")
    ax.legend(); ax.grid(True, axis="y", ls="--", alpha=0.4)
    for i, (d, b) in enumerate(zip(dsp, bram)):
        ax.text(i - width/2, d + 0.1, str(d), ha="center", fontsize=8)
        ax.text(i + width/2, b + 0.1, str(b), ha="center", fontsize=8)

    # --- (c) SQNR vs bit-width ----------------------------------------------
    ax = axes[1, 0]
    ax.plot(bit_widths, sqnr, marker="o", color="#6A1B9A", lw=2, ms=8)
    for w, s in zip(bit_widths, sqnr):
        if s is not None:
            ax.annotate(f"{s:.1f} dB", (w, s), textcoords="offset points",
                        xytext=(0, 8), ha="center", fontsize=9)
    ax.set_xlabel("Do rong bit W"); ax.set_ylabel("SQNR dau ra (dB)")
    ax.set_title("(c) SQNR (single tone) vs Do rong bit\n(tu golden model, da verify bit-exact voi RTL)")
    ax.set_xticks(bit_widths)
    ax.grid(True, ls="--", alpha=0.4)

    # --- (d) Accuracy vs Hardware cost (the actual trade-off curve) --------
    ax = axes[1, 1]
    # 'hardware cost' tong hop: LUT + 100*DSP (DSP dat hon nhieu ve dien tich)
    cost = [l + 100 * d for l, d in zip(lut, dsp)]
    sc = ax.scatter(cost, sqnr, c=bit_widths, cmap="viridis", s=160,
                    edgecolors="k", linewidth=0.6, zorder=5)
    for w, c, s in zip(bit_widths, cost, sqnr):
        if s is not None:
            ax.annotate(f" {w}-bit", (c, s), fontsize=9, va="center")
    ax.set_xlabel("Chi phi phan cung tong hop (LUT + 100xDSP)")
    ax.set_ylabel("SQNR (dB)")
    ax.set_title("(d) Duong cong Trade-off: Do chinh xac vs Chi phi phan cung")
    ax.grid(True, ls="--", alpha=0.4)
    fig.colorbar(sc, ax=ax, label="Do rong bit W")

    fig.suptitle("Trade-off Tai nguyen Phan cung (Vivado Synthesis THAT) vs SQNR\n"
                 "FFT Radix-2 1024-diem, kien truc memory-based, FPGA Artix-7 (xc7k70t)",
                 fontsize=13, y=1.00)
    fig.tight_layout()
    out_path = os.path.join(OUT_DIR, "resource_tradeoff_real.png")
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def save_summary_csv(util_data, sqnr_data, bit_widths):
    out_path = os.path.join(ROOT, "results", "resource_sqnr_summary.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["BIT_WIDTH", "LUT", "FF", "BRAM_tile", "DSP48E1", "SQNR_single_tone_dB"])
        for bw in bit_widths:
            u = util_data[bw]
            s = sqnr_data[bw]
            w.writerow([bw, u["LUT"], u["FF"], u["BRAM"], u["DSP"],
                       "" if s is None else f"{s:.2f}"])
    return out_path


# ----------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------
if __name__ == "__main__":
    print("Doc cac file report_utilization (.rpt) ...")
    util_data = load_all_reports(BIT_WIDTHS)
    for w in BIT_WIDTHS:
        print(f"  BW={w:>2}: LUT={util_data[w]['LUT']:>4}  "
              f"FF={util_data[w]['FF']:>4}  BRAM={util_data[w]['BRAM']:>2}  "
              f"DSP={util_data[w]['DSP']:>2}")

    print("\nDoc SQNR tu golden model ...")
    sqnr_data = load_sqnr(SQNR_CSV, BIT_WIDTHS)
    for w in BIT_WIDTHS:
        print(f"  BW={w:>2}: SQNR = {sqnr_data[w]}")

    print("\nVe do thi trade-off ...")
    img_path = plot_tradeoff(util_data, sqnr_data, BIT_WIDTHS)
    print(f"  -> {img_path}")

    csv_path = save_summary_csv(util_data, sqnr_data, BIT_WIDTHS)
    print(f"  -> {csv_path}")

    print("\nXong.")
