#!/usr/bin/env bash
# ============================================================================
#  run_all.sh -- reproduce the entire FFT bit-width study end to end.
#  Requires: python3 (numpy, matplotlib), iverilog + vvp (Icarus Verilog).
# ============================================================================
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==================================================================="
echo " STEP 1 & 2 : Golden model -> test vectors, twiddle ROM, expected,"
echo "              SQNR table and plots"
echo "==================================================================="
python3 golden_model/golden_model.py
python3 golden_model/gen_bf_vectors.py

echo
echo "==================================================================="
echo " STEP 3a : Verify the radix-2 butterfly (200 bit-exact vectors)"
echo "==================================================================="
cd tb
iverilog -g2012 -o sim_bf tb_butterfly.v ../rtl/butterfly.v ../rtl/complex_mult.v
vvp sim_bf | grep -E "PASS|FAIL"
cd "$ROOT"

echo
echo "==================================================================="
echo " STEP 3b : Verify the full 1024-point FFT core vs golden output"
echo "==================================================================="
cd sim
cp ../test_vectors/twiddle_bw16_cos_hex.txt tw_cos.hex
cp ../test_vectors/twiddle_bw16_sin_hex.txt tw_sin.hex
iverilog -g2012 -o sim_top ../tb/tb_fft_top.v ../rtl/fft_top.v \
         ../rtl/butterfly.v ../rtl/complex_mult.v
for tv in single_tone multi_tone random_noise max_value impulse; do
  cp ../test_vectors/tv_${tv}_bw16_real_hex.txt in_real.hex
  cp ../test_vectors/tv_${tv}_bw16_imag_hex.txt in_imag.hex
  cp ../expected_output/exp_${tv}_bw16_real_hex.txt exp_real.hex
  cp ../expected_output/exp_${tv}_bw16_imag_hex.txt exp_imag.hex
  printf "  %-14s " "$tv"
  vvp sim_top | grep -E "PASS|differ"
done
cd "$ROOT"
echo
echo " DONE. See results/sqnr_results.csv and plots/*.png"
