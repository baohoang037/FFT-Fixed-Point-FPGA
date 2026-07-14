"""
FFT Golden Model & SQNR Analysis (bit-accurate version)
=========================================================
python golden_model.py
"""

import numpy as np
import matplotlib.pyplot as plt
import os
import csv

# ============================================================
# GENERAL CONFIGURATION
# ============================================================
FFT_POINTS  = 1024
BIT_WIDTHS  = [8, 10, 12, 14, 16]
NUM_TRIALS  = 20

DIR_VECTORS = "test_vectors"
DIR_RESULTS = "results"
DIR_PLOTS   = "plots"

for d in [DIR_VECTORS, DIR_RESULTS, DIR_PLOTS]:
    os.makedirs(d, exist_ok=True)

LOG2N = int(np.log2(FFT_POINTS))


# ============================================================
# PART 1: FIXED-POINT (Q1.(W-1), round-half-up, saturate)
# ============================================================

def q_scale(W):
    return 2 ** (W - 1)


def quantize_round(x, W):
    S = q_scale(W)
    max_code = 2 ** (W - 1) - 1
    min_code = -(2 ** (W - 1))
    code = np.floor(x * S + 0.5).astype(np.int64)
    return np.clip(code, min_code, max_code)


def round_div_scale(full_code, W):
    S = q_scale(W)
    return np.floor(full_code / S + 0.5).astype(np.int64)


def halve_round(code):
    return (code + 1) >> 1


def saturate(code, W):
    max_code = 2 ** (W - 1) - 1
    min_code = -(2 ** (W - 1))
    return np.clip(code, min_code, max_code)


# ============================================================
# PART 2: TWIDDLE ROM
# ============================================================

def build_twiddle_rom(N, W):
    k = np.arange(N // 2)
    cos_vals = np.cos(2 * np.pi * k / N)
    sin_vals = np.sin(2 * np.pi * k / N)          # ci = -sin  complex_mult.v
    cos_q = quantize_round(cos_vals, W)
    sin_q = quantize_round(-sin_vals, W)
    return cos_q, sin_q


# ============================================================
# PART 3: BIT-ACCURATE RADIX-2 DIT FFT 
# ============================================================

def bit_reverse_indices(N):
    bits = int(np.log2(N))
    idx = np.arange(N)
    rev = np.zeros(N, dtype=np.int64)
    for i in range(N):
        b = format(i, f'0{bits}b')[::-1]
        rev[i] = int(b, 2)
    return rev


def fixed_point_fft(x_complex, W, N=FFT_POINTS):
    cos_rom, sin_rom = build_twiddle_rom(N, W)

    re = quantize_round(x_complex.real, W)
    im = quantize_round(x_complex.imag, W)

    rev = bit_reverse_indices(N)
    re = re[rev]
    im = im[rev]

    for stage in range(1, LOG2N + 1):
        m = 1 << stage
        half_m = m // 2
        step = N // m
        for k in range(0, N, m):
            for j in range(half_m):
                tw_idx = j * step
                cr = int(cos_rom[tw_idx])
                ci = int(sin_rom[tw_idx])

                idx_a = k + j
                idx_b = k + j + half_m
                br, bi = int(re[idx_b]), int(im[idx_b])
                ar, ai = int(re[idx_a]), int(im[idx_a])

                # complex_mult.v : t = W_N^k . b
                tr_full = cr * br - ci * bi
                ti_full = cr * bi + ci * br
                tr = int(round_div_scale(np.array([tr_full]), W)[0])
                ti = int(round_div_scale(np.array([ti_full]), W)[0])

                # butterfly.v : o0=(a+t+1)>>1 , o1=(a-t+1)>>1 , saturate to W bits
                o0r = int(saturate(halve_round(np.array([ar + tr])), W)[0])
                o0i = int(saturate(halve_round(np.array([ai + ti])), W)[0])
                o1r = int(saturate(halve_round(np.array([ar - tr])), W)[0])
                o1i = int(saturate(halve_round(np.array([ai - ti])), W)[0])

                re[idx_a], im[idx_a] = o0r, o0i
                re[idx_b], im[idx_b] = o1r, o1i

    S = q_scale(W)
    return (re.astype(np.float64) + 1j * im.astype(np.float64)) / S


def calculate_sqnr(fixed_out, golden_scaled):
    signal_power = np.mean(np.abs(golden_scaled) ** 2)
    noise_power  = np.mean(np.abs(golden_scaled - fixed_out) ** 2)
    if noise_power < 1e-20:
        return 999.0
    return 10.0 * np.log10(signal_power / noise_power)


# ============================================================
# PART 4: TEST VECTORS 
# ============================================================

def generate_all_test_vectors(N=FFT_POINTS):
    t = np.arange(N)
    vectors = {}

    f1 = 50.0
    sig = np.sin(2 * np.pi * f1 * t / N)
    vectors['single_tone'] = {'real': sig, 'imag': np.zeros(N)}

    f2 = 120.0
    sig2 = np.sin(2 * np.pi * f1 * t / N) + 0.5 * np.sin(2 * np.pi * f2 * t / N)
    sig2 = sig2 / np.max(np.abs(sig2))
    vectors['multi_tone'] = {'real': sig2, 'imag': np.zeros(N)}

    imp = np.zeros(N); imp[0] = 1.0
    vectors['impulse'] = {'real': imp, 'imag': np.zeros(N)}

    vectors['all_zeros'] = {'real': np.zeros(N), 'imag': np.zeros(N)}

    vectors['full_scale_dc'] = {'real': np.ones(N), 'imag': np.zeros(N)}

    np.random.seed(42)
    vectors['random_noise'] = {
        'real': np.random.randn(N) * 0.25,
        'imag': np.random.randn(N) * 0.25,
    }
    return vectors


# ============================================================
# PART 5: COMPUTE SQNR TABLE (using the bit-accurate FFT above)
# ============================================================

def compute_sqnr_table(vectors, bit_widths, num_trials=NUM_TRIALS):
    results = {name: {} for name in vectors}

    for bw in bit_widths:
        print(f"\n  BIT_WIDTH = {bw}")
        for name, data in vectors.items():

            if name == 'random_noise':
                sqnr_list = []
                for trial in range(num_trials):
                    np.random.seed(trial)
                    real_in = np.random.randn(FFT_POINTS) * 0.25
                    imag_in = np.random.randn(FFT_POINTS) * 0.25
                    x = real_in + 1j * imag_in
                    golden = np.fft.fft(x) / FFT_POINTS
                    fixed_out = fixed_point_fft(x, bw)
                    sqnr_list.append(calculate_sqnr(fixed_out, golden))
                sqnr = float(np.mean(sqnr_list))

            elif name == 'all_zeros':
                sqnr = 999.0

            else:
                x = data['real'] + 1j * data['imag']
                golden = np.fft.fft(x) / FFT_POINTS
                fixed_out = fixed_point_fft(x, bw)
                sqnr = calculate_sqnr(fixed_out, golden)

            results[name][bw] = sqnr
            print(f"    {name:<15}: SQNR = {sqnr:7.2f} dB")

    return results


def save_sqnr_csv(results, bit_widths):
    path = os.path.join(DIR_RESULTS, "sqnr_results.csv")
    with open(path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Test Vector'] + [f'BW={bw}' for bw in bit_widths])
        for name, bw_dict in results.items():
            writer.writerow([name] + [f"{bw_dict[bw]:.2f}" for bw in bit_widths])
    print(f"\n  [OK] SQNR table saved -> {path}")


# ============================================================
# PART 6: NOISE FLOOR / SPECTRUM PLOTS 
# ============================================================

def plot_noise_floor(vectors, bit_widths):
    fig, axes = plt.subplots(len(bit_widths), 1, figsize=(9, 2.6 * len(bit_widths)), sharex=True)
    colors = ['red', 'orange', 'gold', 'green', 'steelblue']

    data = vectors['single_tone']
    x = data['real'] + 1j * data['imag']
    golden = np.fft.fft(x) / FFT_POINTS
    freqs = np.arange(FFT_POINTS // 2)

    for ax, bw, col in zip(axes, bit_widths, colors):
        fixed_out = fixed_point_fft(x, bw)
        err = golden - fixed_out
        err_db = 20 * np.log10(np.abs(err[:FFT_POINTS // 2]) + 1e-20)
        mean_noise_power = np.mean(np.abs(err) ** 2)
        mean_floor = 10 * np.log10(mean_noise_power)
        sqnr = calculate_sqnr(fixed_out, golden)

        ax.plot(freqs, err_db, color=col, linewidth=0.8)
        ax.axhline(mean_floor, color=col, linestyle=':', linewidth=1.5,
                    label=f'Mean noise floor: {mean_floor:.0f} dBFS')
        ax.fill_between(freqs, err_db, mean_floor, alpha=0.08, color=col)
        ax.set_title(f'W = {bw} bit  |  SQNR = {sqnr:.1f} dB', fontsize=11)
        ax.set_ylabel('Error (dBFS)')
        ax.set_ylim(-140, min(20, err_db.max() + 10))
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, linestyle='--', alpha=0.3)

    axes[-1].set_xlabel('Frequency bin index k  (0 to N/2-1)')
    fig.suptitle('Quantization Noise Floor vs. Word Length\nBin-wise error vs. ideal full-precision reference, single tone, N=1024',
                 fontsize=12, y=1.01)
    plt.tight_layout()
    path = os.path.join(DIR_PLOTS, "noise_floor.png")
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Plot saved -> {path}")


def plot_spectrum_comparison(vectors, bit_widths):
    
    fig, axes = plt.subplots(len(bit_widths), 1, figsize=(9, 2.8 * len(bit_widths)), sharex=True)
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#d62728']

    data = vectors['single_tone']
    x = data['real'] + 1j * data['imag']
    golden = np.fft.fft(x) / FFT_POINTS
    golden_db = 20 * np.log10(np.abs(golden[:FFT_POINTS // 2]) + 1e-20)
    freqs = np.arange(FFT_POINTS // 2)

    for ax, bw, col in zip(axes, bit_widths, colors):
        fixed_out = fixed_point_fft(x, bw)
        fixed_db = 20 * np.log10(np.abs(fixed_out[:FFT_POINTS // 2]) + 1e-20)
        err = golden - fixed_out
        noise_floor = 10 * np.log10(np.mean(np.abs(err) ** 2))
        sqnr = calculate_sqnr(fixed_out, golden)

        ax.plot(freqs, fixed_db, color=col, linewidth=0.8, label=f'W = {bw} bit (fixed-point)')
        ax.set_title(f'W = {bw} bit  |  SQNR = {sqnr:.1f} dB  |  Noise floor \u2248 {noise_floor:.0f} dBFS', fontsize=11)
        ax.set_ylabel('Magnitude (dBFS)')
        ax.set_ylim(-150, 5)
        ax.legend(fontsize=8, loc='upper right')
        ax.grid(True, linestyle='--', alpha=0.3)

    axes[-1].set_xlabel('Frequency bin index k  (0 to N/2-1)')
    fig.suptitle('Single-Tone Output Spectrum vs. Word Length\nN = 1024-point FFT  |  Input: single tone at bin 50', fontsize=13, y=1.005)
    plt.tight_layout()
    path = os.path.join(DIR_PLOTS, "spectrum_comparison.png")
    plt.savefig(path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  [OK] Plot saved -> {path}")


def plot_sqnr_tradeoff(results, bit_widths):
    fig, ax = plt.subplots(figsize=(9, 5.5))
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd']
    markers = ['o', 's', '^', 'D']
    plot_names = ['single_tone', 'multi_tone', 'full_scale_dc', 'random_noise']
    labels = ['Single tone', 'Multi tone', 'Full-scale DC', 'Random noise (avg)']

    theory_bw = np.linspace(7, 17, 100)
    theory_sqnr = 6.02 * theory_bw + 1.76
    ax.plot(theory_bw, theory_sqnr, '--', color='gray', linewidth=1.2,
            label='Input-only bound: 6.02W + 1.76 dB', zorder=1)

    for name, label, col, mk in zip(plot_names, labels, colors, markers):
        vals = [results[name][bw] for bw in bit_widths]
        ax.plot(bit_widths, vals, color=col, marker=mk, linewidth=2, markersize=7, label=label, zorder=3)
        for bw, v in zip(bit_widths, vals):
            ax.annotate(f'{v:.1f}', (bw, v), textcoords="offset points", xytext=(0, 8), fontsize=8, ha='center')

    ax.axhspan(0, 30, alpha=0.05, color='red')
    ax.axhspan(30, 50, alpha=0.05, color='orange')
    ax.axhspan(50, 105, alpha=0.05, color='green')
    ax.text(16.3, 15, 'Low quality\n(<30 dB)', fontsize=8, color='#a03030', ha='right')
    ax.text(16.3, 40, 'Moderate quality\n(30-50 dB)', fontsize=8, color='#a06a10', ha='right')
    ax.text(16.3, 90, 'High quality\n(>50 dB)', fontsize=8, color='#2a7a2a', ha='right')

    ax.set_xlabel('Data word length W (bits)', fontsize=12)
    ax.set_ylabel('Output SQNR (dB)', fontsize=12)
    ax.set_title('Output SQNR vs. Word Length\nFixed-Point Radix-2 DIT FFT, N = 1024, Scaled Architecture', fontsize=13)
    ax.set_xticks(bit_widths)
    ax.grid(True, linestyle='--', alpha=0.4)
    ax.legend(fontsize=9, loc='upper left')
    plt.tight_layout()
    path = os.path.join(DIR_PLOTS, "sqnr_vs_bitwidth.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  [OK] Plot saved -> {path}")


def plot_resource_tradeoff_real(sqnr_single_tone, vivado_lut, vivado_dsp, bit_widths):
    fig, ax = plt.subplots(figsize=(8, 6.5))
    cost = [lut + 100 * dsp for lut, dsp in zip(vivado_lut, vivado_dsp)]
    sc = ax.scatter(cost, sqnr_single_tone, c=bit_widths, cmap='viridis', s=200,
                     edgecolors='black', linewidth=1.2, zorder=3)
    for bw, c, s in zip(bit_widths, cost, sqnr_single_tone):
        ax.annotate(f'{bw}-bit\n({s:.1f} dB)', (c, s), textcoords="offset points",
                    xytext=(12, 0), fontsize=9, va='center')
    cbar = plt.colorbar(sc)
    cbar.set_label('Word length W (bits)')
    ax.set_xlabel('Combined hardware cost  (LUT + 100 x DSP48E1)', fontsize=11)
    ax.set_ylabel('Output SQNR -- single tone (dB)', fontsize=11)
    ax.set_title('Accuracy vs. Hardware Cost Trade-off\nFixed-Point FFT, N = 1024, Artix-7 xc7k70t', fontsize=12)
    ax.grid(True, linestyle='--', alpha=0.4)
    plt.tight_layout()
    path = os.path.join(DIR_PLOTS, "resource_tradeoff_real.png")
    plt.savefig(path, dpi=150)
    plt.close()
    print(f"  [OK] Plot saved -> {path}")


if __name__ == "__main__":
    vectors = generate_all_test_vectors(FFT_POINTS)
    results = compute_sqnr_table(vectors, BIT_WIDTHS)
    save_sqnr_csv(results, BIT_WIDTHS)
    plot_noise_floor(vectors, BIT_WIDTHS)
    plot_spectrum_comparison(vectors, BIT_WIDTHS)
    plot_sqnr_tradeoff(results, BIT_WIDTHS)

    # So lieu Vivado that (tu Table II trong bai bao, post-synthesis)
    vivado_lut = [581, 829, 341, 366, 383]
    vivado_dsp = [0, 0, 5, 5, 5]
    sqnr_single = [results['single_tone'][bw] for bw in BIT_WIDTHS]
    plot_resource_tradeoff_real(sqnr_single, vivado_lut, vivado_dsp, BIT_WIDTHS)