"""
================================================================================
 FFT Golden Model & Finite-Word-Length (SQNR) Analysis  -- CORRECTED VERSION
================================================================================
 Project : Evaluating Bit-Width Trade-offs for Fixed-Point Radix-2 FFT on FPGA
 Role    : Verification / DSP modelling (golden reference for RTL)

 WHAT CHANGED vs the first draft (and WHY it matters)
 ----------------------------------------------------------------------------
 1. The old model only quantized the INPUT and then ran a floating-point
    np.fft.fft(). That measures ONLY input quantization noise, so every curve
    collapsed onto the textbook 6.02N+1.76 dB line. The whole research question
    (noise that ACCUMULATES inside the fixed-point FFT) was never modelled.
    => Here we implement a bit-accurate, integer radix-2 DIT FFT with:
         - quantized twiddle factors  (Qt = 1.(TW-1))
         - rounding after every complex multiply
         - 1/2 scaling (right shift) after every butterfly stage (overflow-safe)
       Noise is injected at all 10 stages, exactly like the hardware.

 2. impulse / all_zeros / max_value used to return SQNR = 999, which pushed the
    trade-off plot y-axis to 1000 dB and made it unreadable.
    => all_zeros has zero signal power (SQNR undefined) and is reported as a
       functional/reset test, not an SQNR data point. Other vectors now give
       finite, realistic SQNR because twiddle/rounding noise is modelled.

 3. The hex test-vector files (loaded by the RTL via $readmemh) were ROUNDED
    while the float files / SQNR used TRUNCATION -> the testbench would have
    compared against a mismatched golden.
    => One single quantizer (round-half-up) is used everywhere now.

 4. Twiddle ROM files were never generated (a required deliverable).
    => twiddle_bwXX_{cos,sin}_hex.txt are produced for $readmemh.

 5. Fractional format is now Q1.(W-1) (full dynamic range), and the per-stage
    1/2 scaling keeps every intermediate strictly inside [-1, 1).

 Run:  python golden_model.py
================================================================================
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os, csv

# ----------------------------------------------------------------------------
# GLOBAL CONFIGURATION
# ----------------------------------------------------------------------------
FFT_POINTS = 1024                      # N (must be a power of two)
STAGES     = int(np.log2(FFT_POINTS))  # 10
BIT_WIDTHS = [8, 10, 12, 14, 16]       # data word lengths under test
TW_BITS    = None                      # twiddle width; None => same as data BW
ROUND_MODE = "RND"                     # "RND" (round half-up) or "TRN" (floor)
SAMPLE_RATE = 1024.0                   # Hz, only for axis labelling
NUM_TRIALS  = 30                       # Monte-Carlo trials for random-noise SQNR
PEAK        = 0.90                     # signals scaled to +/-0.90 (headroom)

# Output directories (relative to where the script runs)
BASE        = os.path.dirname(os.path.abspath(__file__))
ROOT        = os.path.dirname(BASE)
DIR_VECTORS = os.path.join(ROOT, "test_vectors")
DIR_EXPECT  = os.path.join(ROOT, "expected_output")
DIR_RESULTS = os.path.join(ROOT, "results")
DIR_PLOTS   = os.path.join(ROOT, "plots")
for d in (DIR_VECTORS, DIR_EXPECT, DIR_RESULTS, DIR_PLOTS):
    os.makedirs(d, exist_ok=True)


# ============================================================================
# 1. FIXED-POINT PRIMITIVES  (integer / bit-accurate, Q1.(W-1) format)
# ============================================================================

def q_round(x_scaled, mode=ROUND_MODE):
    """Round a real-valued scaled quantity to the nearest integer code."""
    if mode == "TRN":
        return np.floor(x_scaled)
    return np.floor(x_scaled + 0.5)          # round half-up (cheap in HW)


def float_to_code(x, W, mode=ROUND_MODE):
    """
    Quantize float array x (assumed in [-1,1)) to W-bit two's-complement codes,
    format Q1.(W-1).  Returns int64 codes, saturated to the legal range.
    """
    frac   = W - 1
    maxc   =  (1 << (W - 1)) - 1
    minc   = -(1 << (W - 1))
    code   = q_round(np.asarray(x, dtype=np.float64) * (1 << frac), mode)
    return np.clip(code, minc, maxc).astype(np.int64)


def code_to_float(code, W):
    """Convert integer codes back to real values (Q1.(W-1))."""
    return np.asarray(code, dtype=np.float64) / (1 << (W - 1))


def sat(code, W):
    """Saturate integer codes to W-bit two's-complement range."""
    return np.clip(code, -(1 << (W - 1)), (1 << (W - 1)) - 1)


def to_hex(code, W):
    """Integer code -> zero-padded two's-complement hex string for $readmemh."""
    code = int(code) & ((1 << W) - 1)
    ndig = (W + 3) // 4
    return format(code, f"0{ndig}X")


# ============================================================================
# 2. QUANTIZED TWIDDLE FACTORS
# ============================================================================

def make_twiddle_codes(N, TW):
    """
    W_N^k = cos(2*pi*k/N) - j*sin(2*pi*k/N), k = 0 .. N/2-1.
    Quantized to TW-bit Q1.(TW-1) integer codes (cos and sin tables).
    +1.0 saturates to the largest positive code (max = 1 - 2^-(TW-1)).
    """
    k   = np.arange(N // 2)
    cos = np.cos(2 * np.pi * k / N)
    sin = np.sin(2 * np.pi * k / N)
    cos_c = float_to_code(cos, TW)
    sin_c = float_to_code(sin, TW)
    return cos_c, sin_c


# ============================================================================
# 3. BIT-ACCURATE FIXED-POINT RADIX-2 DIT FFT
# ============================================================================

def _bit_reverse(indices, bits):
    rev = np.zeros_like(indices)
    for i in indices:
        r = 0
        x = i
        for _ in range(bits):
            r = (r << 1) | (x & 1)
            x >>= 1
        rev[i] = r
    return rev


def fft_fixed(xr_code, xi_code, W, TW, mode=ROUND_MODE):
    """
    Bit-accurate radix-2 Decimation-in-Time FFT on integer codes.

    Data path : Q1.(W-1).  Twiddles : Q1.(TW-1).
    Per stage : after the butterfly add/sub we shift right by 1 (divide by 2,
                with rounding) to guarantee no overflow. After 'STAGES' stages
                the result is the true DFT scaled by 1/N -- the standard
                "scaled" fixed-point FFT used in real hardware.

    Returns (Xr_code, Xi_code) integer codes in Q1.(W-1) representing X[k]/N.
    """
    N      = len(xr_code)
    bits   = int(np.log2(N))
    frac_t = TW - 1                         # twiddle fractional bits

    # bit-reversal reorder (DIT, natural-order output)
    order  = _bit_reverse(np.arange(N), bits)
    ar = sat(np.array(xr_code, dtype=np.int64)[order], W)
    ai = sat(np.array(xi_code, dtype=np.int64)[order], W)

    cos_c, sin_c = make_twiddle_codes(N, TW)

    half_lsb = (1 << (frac_t - 1)) if mode == "RND" else 0   # rounding for mult
    m = 1
    for _stage in range(bits):
        m  <<= 1                              # current sub-FFT size
        hm  = m >> 1
        step = N // m                         # twiddle index stride
        for k in range(0, N, m):
            for j in range(hm):
                ti = j * step                  # twiddle index
                cr = int(cos_c[ti]); ci = -int(sin_c[ti])   # W_N^ti = cos - j sin

                br = int(ar[k + j + hm]); bi = int(ai[k + j + hm])
                # complex multiply t = W * b  (Q1.(W-1) result, rounded)
                tr = (cr * br - ci * bi + half_lsb) >> frac_t
                ti_ = (cr * bi + ci * br + half_lsb) >> frac_t

                ur = int(ar[k + j]); ui = int(ai[k + j])

                # butterfly + 1/2 scaling (round half-up on the shift)
                add = 1 if mode == "RND" else 0
                o0r = (ur + tr + add) >> 1
                o0i = (ui + ti_ + add) >> 1
                o1r = (ur - tr + add) >> 1
                o1i = (ui - ti_ + add) >> 1

                ar[k + j]      = max(min(o0r, (1 << (W-1)) - 1), -(1 << (W-1)))
                ai[k + j]      = max(min(o0i, (1 << (W-1)) - 1), -(1 << (W-1)))
                ar[k + j + hm] = max(min(o1r, (1 << (W-1)) - 1), -(1 << (W-1)))
                ai[k + j + hm] = max(min(o1i, (1 << (W-1)) - 1), -(1 << (W-1)))
    return ar, ai


# ============================================================================
# 4. SQNR
# ============================================================================

def sqnr_db(fixed_complex, ref_complex):
    """10*log10( signal_power / noise_power ). Returns np.inf if no noise,
    np.nan if the reference has (essentially) zero power."""
    sig = np.mean(np.abs(ref_complex) ** 2)
    if sig < 1e-30:
        return np.nan
    noise = np.mean(np.abs(ref_complex - fixed_complex) ** 2)
    if noise < 1e-30:
        return np.inf
    return 10.0 * np.log10(sig / noise)


def run_fixed_fft_on_float(x_complex, W, TW, mode=ROUND_MODE):
    """Quantize a complex float input, run the fixed FFT, return float output
    (already representing X[k]/N) so it can be compared with np.fft.fft(x)/N."""
    xr = float_to_code(x_complex.real, W, mode)
    xi = float_to_code(x_complex.imag, W, mode)
    Xr, Xi = fft_fixed(xr, xi, W, TW, mode)
    return code_to_float(Xr, W) + 1j * code_to_float(Xi, W)


# ============================================================================
# 5. TEST VECTORS
# ============================================================================

def generate_test_vectors(N=FFT_POINTS):
    t = np.arange(N)
    v = {}

    f1 = 50
    s = np.sin(2 * np.pi * f1 * t / N)
    v["single_tone"] = dict(real=PEAK * s, imag=np.zeros(N),
        desc=f"Single tone, bin {f1}")

    f2 = 120
    s = np.sin(2 * np.pi * f1 * t / N) + 0.5 * np.sin(2 * np.pi * f2 * t / N)
    s = s / np.max(np.abs(s))
    v["multi_tone"] = dict(real=PEAK * s, imag=np.zeros(N),
        desc=f"Two tones, bins {f1} & {f2} (linearity)")

    imp = np.zeros(N); imp[0] = 0.5
    v["impulse"] = dict(real=imp, imag=np.zeros(N),
        desc="Unit impulse -> flat magnitude spectrum")

    v["all_zeros"] = dict(real=np.zeros(N), imag=np.zeros(N),
        desc="All zeros -> reset / boundary functional test")

    v["max_value"] = dict(real=np.full(N, PEAK), imag=np.zeros(N),
        desc="Near-full-scale DC -> saturation / overflow test")

    rng = np.random.default_rng(42)
    g = rng.standard_normal(N) + 1j * rng.standard_normal(N)
    g = PEAK * g / np.max(np.abs(np.concatenate([g.real, g.imag])))
    v["random_noise"] = dict(real=g.real, imag=g.imag,
        desc="Complex Gaussian (statistical SQNR)")
    return v


# ============================================================================
# 6. SAVE INPUT VECTORS, TWIDDLE ROM, EXPECTED OUTPUT
# ============================================================================

def save_inputs_and_expected(vectors, W, TW):
    for name, d in vectors.items():
        xr = float_to_code(d["real"], W)
        xi = float_to_code(d["imag"], W)
        base = os.path.join(DIR_VECTORS, f"tv_{name}_bw{W}")
        with open(base + "_float.txt", "w") as f:
            f.write(f"// {d['desc']}\n// BIT_WIDTH={W}, Q1.{W-1}, round-half-up\n")
            f.write("// real imag (one complex sample per line)\n")
            for r, i in zip(code_to_float(xr, W), code_to_float(xi, W)):
                f.write(f"{r:.10f} {i:.10f}\n")
        with open(base + "_real_hex.txt", "w") as f:
            f.writelines(to_hex(c, W) + "\n" for c in xr)
        with open(base + "_imag_hex.txt", "w") as f:
            f.writelines(to_hex(c, W) + "\n" for c in xi)

        # expected fixed-point FFT output (golden for the self-checking TB)
        Xr, Xi = fft_fixed(xr, xi, W, TW)
        ebase = os.path.join(DIR_EXPECT, f"exp_{name}_bw{W}")
        with open(ebase + "_real_hex.txt", "w") as f:
            f.writelines(to_hex(c, W) + "\n" for c in Xr)
        with open(ebase + "_imag_hex.txt", "w") as f:
            f.writelines(to_hex(c, W) + "\n" for c in Xi)

    # twiddle ROM (one per width, independent of test vector)
    cos_c, sin_c = make_twiddle_codes(FFT_POINTS, TW)
    with open(os.path.join(DIR_VECTORS, f"twiddle_bw{TW}_cos_hex.txt"), "w") as f:
        f.writelines(to_hex(c, TW) + "\n" for c in cos_c)
    with open(os.path.join(DIR_VECTORS, f"twiddle_bw{TW}_sin_hex.txt"), "w") as f:
        f.writelines(to_hex(c, TW) + "\n" for c in sin_c)


# ============================================================================
# 7. SQNR TABLE
# ============================================================================

def compute_sqnr(vectors, bit_widths):
    res = {n: {} for n in vectors}
    for W in bit_widths:
        TW = W if TW_BITS is None else TW_BITS
        for name, d in vectors.items():
            if name == "all_zeros":
                res[name][W] = np.nan
                continue
            if name == "random_noise":
                vals = []
                rng = np.random.default_rng(1000)
                for _ in range(NUM_TRIALS):
                    g = rng.standard_normal(FFT_POINTS) + 1j * rng.standard_normal(FFT_POINTS)
                    g = PEAK * g / np.max(np.abs(np.concatenate([g.real, g.imag])))
                    ref = np.fft.fft(g) / FFT_POINTS
                    fx  = run_fixed_fft_on_float(g, W, TW)
                    vals.append(sqnr_db(fx, ref))
                res[name][W] = float(np.mean(vals))
            else:
                x   = d["real"] + 1j * d["imag"]
                ref = np.fft.fft(x) / FFT_POINTS
                fx  = run_fixed_fft_on_float(x, W, TW)
                res[name][W] = sqnr_db(fx, ref)
    return res


def save_csv(res, bit_widths):
    path = os.path.join(DIR_RESULTS, "sqnr_results.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Test Vector"] + [f"BW={b}" for b in bit_widths])
        for name, bw in res.items():
            row = [name]
            for b in bit_widths:
                v = bw[b]
                row.append("nan" if np.isnan(v) else ("inf" if np.isinf(v) else f"{v:.2f}"))
            w.writerow(row)
    return path


# ============================================================================
# 8. PLOTS
# ============================================================================

def plot_tradeoff(res, bit_widths):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    series = [("single_tone", "Single tone", "o", "#1565C0"),
              ("multi_tone",  "Multi tone",  "s", "#EF6C00"),
              ("max_value",   "Full-scale DC", "^", "#2E7D32"),
              ("random_noise","Random noise (avg)", "D", "#6A1B9A")]
    for key, lab, mk, col in series:
        y = [res[key][b] for b in bit_widths]
        y = [np.nan if (np.isinf(v) or np.isnan(v)) else v for v in y]
        ax.plot(bit_widths, y, marker=mk, color=col, lw=2, ms=7, label=lab, zorder=3)

    th = np.linspace(7.5, 16.5, 50)
    ax.plot(th, 6.02 * th + 1.76, "--", color="gray", lw=1.2,
            label="Input-only bound 6.02N+1.76", zorder=1)

    ax.axhspan(0, 30,  color="red",    alpha=0.05)
    ax.axhspan(30, 50, color="orange", alpha=0.05)
    ax.axhspan(50, 110,color="green",  alpha=0.05)
    ax.set(xlabel="Data word length W (bit)", ylabel="Output SQNR (dB)",
           title="SQNR vs Word Length — Scaled Radix-2 FFT (N=1024)")
    ax.set_xticks(bit_widths); ax.set_xlim(7.5, 16.5); ax.set_ylim(0, 105)
    ax.grid(True, ls="--", alpha=0.4); ax.legend(fontsize=9, loc="upper left")
    fig.tight_layout()
    p = os.path.join(DIR_PLOTS, "sqnr_vs_bitwidth.png")
    fig.savefig(p, dpi=150); plt.close(fig); return p


def plot_spectrum(vectors, bit_widths):
    fig, axes = plt.subplots(len(bit_widths), 1,
                             figsize=(10, 2.6 * len(bit_widths)), sharex=True)
    d = vectors["single_tone"]
    x = d["real"] + 1j * d["imag"]
    ref = np.fft.fft(x) / FFT_POINTS
    ref_db = 20 * np.log10(np.abs(ref[:FFT_POINTS // 2]) + 1e-12)
    fr = np.arange(FFT_POINTS // 2)
    for bw, ax in zip(bit_widths, axes):
        TW = bw if TW_BITS is None else TW_BITS
        fx = run_fixed_fft_on_float(x, bw, TW)
        fx_db = 20 * np.log10(np.abs(fx[:FFT_POINTS // 2]) + 1e-12)
        s = sqnr_db(fx, ref)
        ax.plot(fr, ref_db, color="lightgray", lw=1.0, label="Floating-point ref")
        ax.plot(fr, fx_db, color="#1565C0", lw=0.9, label=f"{bw}-bit fixed")
        ax.set_title(f"W = {bw} bit   |   SQNR = {s:.1f} dB", fontsize=10)
        ax.set_ylabel("dBFS", fontsize=9); ax.set_ylim(-140, 5)
        ax.grid(True, ls="--", alpha=0.3); ax.legend(fontsize=8, loc="upper right")
    axes[-1].set_xlabel("Frequency bin k")
    fig.suptitle("Single-Tone Spectrum vs Word Length (noise floor rises as W drops)",
                 y=1.005, fontsize=12)
    fig.tight_layout()
    p = os.path.join(DIR_PLOTS, "spectrum_comparison.png")
    fig.savefig(p, dpi=150, bbox_inches="tight"); plt.close(fig); return p


def plot_noise_floor(vectors, bit_widths):
    fig, ax = plt.subplots(figsize=(9, 5))
    cols = ["#E53935", "#FB8C00", "#FDD835", "#43A047", "#1E88E5"]
    d = vectors["single_tone"]; x = d["real"] + 1j * d["imag"]
    ref = np.fft.fft(x) / FFT_POINTS
    fr = np.arange(FFT_POINTS // 2)
    for bw, c in zip(bit_widths, cols):
        TW = bw if TW_BITS is None else TW_BITS
        fx = run_fixed_fft_on_float(x, bw, TW)
        err = 20 * np.log10(np.abs((ref - fx)[:FFT_POINTS // 2]) + 1e-12)
        ax.plot(fr, err, color=c, lw=0.8, alpha=0.85, label=f"{bw}-bit")
    ax.set(xlabel="Frequency bin k", ylabel="Quantization error (dBFS)",
           title="In-band Quantization Noise Floor vs Word Length")
    ax.grid(True, ls="--", alpha=0.4); ax.legend(title="W")
    fig.tight_layout()
    p = os.path.join(DIR_PLOTS, "noise_floor.png")
    fig.savefig(p, dpi=150); plt.close(fig); return p


def plot_resource_tradeoff(res, bit_widths):
    """
    Analytical first-order resource model (clearly labelled as ESTIMATE).
    Replace lut/dsp/bram/power lists with real Vivado numbers when available.
    Complex multiplier area ~ W^2 (DSP), datapath/registers ~ W (LUT/FF),
    delay-line memory ~ W (BRAM).
    """
    ref = 16.0
    lut  = [100 * (b / ref)       for b in bit_widths]
    dsp  = [100 * (b / ref) ** 2  for b in bit_widths]
    bram = [100 * (b / ref)       for b in bit_widths]
    sqnr = [res["random_noise"][b] for b in bit_widths]

    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 5))
    x = np.arange(len(bit_widths)); wdt = 0.25
    a1.bar(x - wdt, lut,  wdt, label="LUT/FF ~ W",  color="#1E88E5")
    a1.bar(x,       dsp,  wdt, label="DSP ~ W^2",   color="#E53935")
    a1.bar(x + wdt, bram, wdt, label="BRAM ~ W",    color="#43A047")
    a1.set_xticks(x); a1.set_xticklabels([f"{b}b" for b in bit_widths])
    a1.set_ylabel("Relative resource (%, vs 16-bit)")
    a1.set_title("First-order FPGA resource model\n(ESTIMATE — replace w/ Vivado)")
    a1.legend(fontsize=9); a1.grid(True, axis="y", ls="--", alpha=0.4)

    sc = a2.scatter(dsp, sqnr, s=140, c=bit_widths, cmap="viridis",
                    edgecolors="k", linewidth=0.5, zorder=5)
    for b, dd, ss in zip(bit_widths, dsp, sqnr):
        a2.annotate(f" {b}-bit", (dd, ss), fontsize=10, va="center")
    a2.set(xlabel="Relative DSP cost (%, ~W^2)", ylabel="SQNR (dB)",
           title="Accuracy vs Multiplier Cost — pick the knee")
    a2.grid(True, ls="--", alpha=0.4)
    fig.colorbar(sc, ax=a2, label="W (bit)")
    fig.tight_layout()
    p = os.path.join(DIR_PLOTS, "resource_tradeoff.png")
    fig.savefig(p, dpi=150); plt.close(fig); return p


# ============================================================================
# 9. SUMMARY
# ============================================================================

def print_table(res, bit_widths):
    print("\n" + "=" * 78)
    print("  OUTPUT SQNR (dB) — Scaled Fixed-Point Radix-2 FFT, N =", FFT_POINTS)
    print("=" * 78)
    print(f"  {'Test Vector':<16}" + "".join(f"{b:>9}b" for b in bit_widths))
    print("-" * 78)
    for name, bw in res.items():
        row = f"  {name:<16}"
        for b in bit_widths:
            v = bw[b]
            row += f"{'  N/A':>10}" if np.isnan(v) else (
                   f"{'  inf':>10}" if np.isinf(v) else f"{v:>10.2f}")
        print(row)
    print("-" * 78)
    print("  Input-only bound 6.02W+1.76:" )
    print(f"  {'':<16}" + "".join(f"{6.02*b+1.76:>10.1f}" for b in bit_widths))
    print("=" * 78)
    print("\n  Per-doubling-of-N rule of thumb: scaled radix-2 FFT loses a few dB")
    print("  of SQNR every time N doubles -> the gap below the input-only bound")
    print("  is the accumulated twiddle + rounding noise this model now captures.")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  FIXED-POINT FFT GOLDEN MODEL  (corrected finite-word-length)")
    print("=" * 60)

    print("\n[1/4] Generating test vectors, twiddle ROM, expected outputs ...")
    vectors = generate_test_vectors()
    for W in BIT_WIDTHS:
        TW = W if TW_BITS is None else TW_BITS
        save_inputs_and_expected(vectors, W, TW)
    print(f"      {len(vectors)} signals x {len(BIT_WIDTHS)} widths written.")

    print("\n[2/4] Computing SQNR (bit-accurate FFT, twiddle+rounding noise) ...")
    res = compute_sqnr(vectors, BIT_WIDTHS)
    csvp = save_csv(res, BIT_WIDTHS)
    print_table(res, BIT_WIDTHS)
    print(f"\n      CSV -> {csvp}")

    print("\n[3/4] Plotting ...")
    for p in (plot_tradeoff(res, BIT_WIDTHS),
              plot_spectrum(vectors, BIT_WIDTHS),
              plot_noise_floor(vectors, BIT_WIDTHS),
              plot_resource_tradeoff(res, BIT_WIDTHS)):
        print("      ->", p)

    print("\n[4/4] Done.")
