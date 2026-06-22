# FFT Fixed-Point FPGA — Đánh giá Trade-off Độ rộng Bit

**Đề tài NCKH:** Evaluating Bit-Width Trade-offs for Fixed-Point Radix-2 DIT FFT on FPGA

**Mục tiêu:** Xây dựng và kiểm chứng bộ FFT Radix-2 số điểm cố định tham số hóa theo độ rộng bit (W = 8/10/12/14/16), đo đạc thực nghiệm sự đánh đổi giữa chất lượng tín hiệu (SQNR) và chi phí tài nguyên phần cứng (LUT/FF/DSP/BRAM) trên FPGA Artix-7.

---

## Cấu trúc project

```
FFT-Fixed-Point-FPGA/
├── golden_model/
│   ├── golden_model.py           # Mô hình FFT bit-accurate (số điểm cố định)
│   ├── gen_bf_vectors.py         # Sinh vector kiểm tra cho butterfly
│   └── plot_resource_tradeoff.py # Vẽ đồ thị trade-off từ số liệu Vivado thật
│
├── rtl/
│   ├── complex_mult.v            # Bộ nhân phức Q1.(W-1) x Q1.(TW-1)
│   ├── butterfly.v               # Butterfly Radix-2 DIT + scaling 1/2
│   ├── twiddle_rom.v             # ROM hệ số xoay (readmemh)
│   ├── fft_top.v                 # FFT 1024 điểm, memory-based, FSM
│   └── fft_top.xdc               # Timing constraint (clock 100 MHz)
│
├── tb/
│   ├── tb_butterfly.v            # Testbench tự kiểm tra butterfly (200 vector)
│   └── tb_fft_top.v              # Testbench tự kiểm tra FFT 1024 điểm
│
├── vivado_reports/
│   ├── util_bw8.rpt              # Báo cáo Utilization Vivado — W=8
│   ├── util_bw10.rpt             # Báo cáo Utilization Vivado — W=10
│   ├── util_bw12.rpt             # Báo cáo Utilization Vivado — W=12
│   ├── util_bw14.rpt             # Báo cáo Utilization Vivado — W=14
│   └── util_bw16.rpt             # Báo cáo Utilization Vivado — W=16
│
├── results/
│   ├── sqnr_results.csv          # SQNR theo bit-width và loại tín hiệu
│   └── resource_sqnr_summary.csv # Bảng tổng hợp tài nguyên + SQNR
│
├── plots/
│   ├── sqnr_vs_bitwidth.png      # SQNR vs W cho 4 loại tín hiệu
│   ├── spectrum_comparison.png   # Phổ tần số single-tone qua 5 bit-width
│   ├── noise_floor.png           # Noise floor lượng tử hóa theo bin tần số
│   └── resource_tradeoff_real.png # Trade-off tài nguyên thật vs SQNR
│
└── references/
    └── references.md             # Danh sách tài liệu tham khảo
```

---

## Kết quả chính

### SQNR đầu ra (dB) — N=1024, Scaled Radix-2 FFT

| Tín hiệu | W=8 | W=10 | W=12 | W=14 | W=16 |
|---|---|---|---|---|---|
| Single tone | 10.2 | 22.1 | 34.4 | 46.3 | 58.4 |
| Multi tone | 7.2 | 19.8 | 31.2 | 43.5 | 55.4 |
| Full-scale DC | 15.3 | 27.3 | 39.4 | 51.4 | 63.4 |
| Random noise | 2.5 | 14.5 | 26.5 | 38.5 | 50.6 |

SQNR tăng xấp xỉ **6 dB mỗi bit**, thấp hơn cận input-only (6.02W+1.76) khoảng 40 dB — đây là phần nhiễu tích lũy bên trong FFT mà mô hình chỉ lượng tử đầu vào bỏ sót.

### Tài nguyên phần cứng thật (Vivado Synthesis, Artix-7 xc7k70t)

| W | LUT | FF | BRAM (tile) | DSP48E1 |
|---|---|---|---|---|
| 8 | 581 | 138 | 2 | 0 |
| 10 | 829 | 146 | 2 | 0 |
| 12 | 341 | 154 | 2 | 5 |
| 14 | 366 | 162 | 2 | 5 |
| 16 | 383 | 170 | 2 | 5 |

**Quan sát:** Ở W=8/10, Vivado suy luận bộ nhân phức bằng LUT thuần (DSP=0) vì toán hạng nhỏ không đủ để tận dụng DSP48E1. Từ W=12 trở lên, công cụ chuyển sang dùng DSP (5 khối, cố định vì kiến trúc dùng chung 1 butterfly) và LUT giảm mạnh — đây là điểm "gãy" trong đường cong chi phí phần cứng.

---

## Hướng dẫn tái tạo kết quả

### 1. Cài đặt

```bash
pip install numpy matplotlib
```

### 2. Sinh test vector và tính SQNR

```bash
cd golden_model
python golden_model.py
python gen_bf_vectors.py
```

Kết quả: `results/sqnr_results.csv`, `plots/sqnr_vs_bitwidth.png`, `plots/spectrum_comparison.png`, `plots/noise_floor.png`, cùng toàn bộ file hex test vector và expected output.

### 3. Mô phỏng RTL (cần Icarus Verilog)

```bash
# Kiểm tra butterfly (200 vector bit-exact)
cd tb
iverilog -g2012 -o sim_bf tb_butterfly.v ../rtl/butterfly.v ../rtl/complex_mult.v
vvp sim_bf

# Kiểm tra FFT 1024 điểm (5 tín hiệu, W=16)
cd ../sim
cp ../test_vectors/twiddle_bw16_cos_hex.txt tw_cos.hex
cp ../test_vectors/twiddle_bw16_sin_hex.txt tw_sin.hex
cp ../test_vectors/tv_single_tone_bw16_real_hex.txt in_real.hex
cp ../test_vectors/tv_single_tone_bw16_imag_hex.txt in_imag.hex
cp ../expected_output/exp_single_tone_bw16_real_hex.txt exp_real.hex
cp ../expected_output/exp_single_tone_bw16_imag_hex.txt exp_imag.hex
iverilog -g2012 -o sim_top ../tb/tb_fft_top.v ../rtl/fft_top.v ../rtl/butterfly.v ../rtl/complex_mult.v
vvp sim_top
```

Kết quả mong đợi:
```
BUTTERFLY PASS: all 200 vectors bit-exact vs golden
FFT_TOP PASS: all 1024 bins bit-exact vs golden
```

### 4. Vẽ đồ thị trade-off từ số liệu Vivado thật

Đặt 5 file `util_bwX.rpt` (từ thư mục `vivado_reports/`) vào thư mục `golden_model/`, rồi chạy:

```bash
cd golden_model
python plot_resource_tradeoff.py
```

Kết quả: `plots/resource_tradeoff_real.png`, `results/resource_sqnr_summary.csv`.

---

## Thông số thiết kế

| Thông số | Giá trị |
|---|---|
| Số điểm FFT (N) | 1024 |
| Thuật toán | Radix-2 Decimation-in-Time (DIT) |
| Kiến trúc | Memory-based, dùng chung 1 butterfly |
| Định dạng số | Q1.(W-1) two's complement |
| Chống tràn | Scaling cố định 1/2 sau mỗi tầng |
| Hệ số xoay | Lượng tử hóa Q1.(W-1), nạp bằng $readmemh |
| FPGA mục tiêu | Xilinx Artix-7 (xc7k70tfbv676-1) |
| Công cụ | Vivado 2018.3, Python 3.x |

---

## Kết quả kiểm chứng

- ✅ Butterfly: **bit-exact 200/200 vector** so với golden model
- ✅ FFT 1024 điểm: **bit-exact 1024/1024 bin** cho 5 loại tín hiệu (W=12 và W=16)
- ✅ Synthesis: **0 error, 0 critical warning** cho cả 5 cấu hình bit-width
- ✅ BRAM inference thành công (RAMB18E1, không bị "dissolved into registers")

---

## Tác giả

Nhóm nghiên cứu NCKH — Khoa Điện–Điện tử, [Tên trường]