# References

Selected references for the research topic:
**"Evaluating Bit-Width Trade-offs for Fixed-Point Radix-2 DIT FFT on FPGA"**

---

## I. FFT Algorithm and Fixed-Point Arithmetic Theory

[1] J. W. Cooley and J. W. Tukey, "An algorithm for the machine calculation of complex Fourier series," *Mathematics of Computation*, vol. 19, no. 90, pp. 297–301, Apr. 1965.
> The original Cooley–Tukey FFT paper. Fundamental reference for the Radix-2 DIT algorithm used in this work.

[2] A. V. Oppenheim and R. W. Schafer, *Discrete-Time Signal Processing*, 3rd ed. Upper Saddle River, NJ: Pearson Prentice Hall, 2010.
> Chapters 8–9 cover the FFT algorithm derivation and finite word-length effects (quantization noise, overflow, scaling).

[3] W. Chang and T. Q. Nguyen, "On the fixed-point accuracy analysis of FFT algorithms," *IEEE Transactions on Signal Processing*, vol. 56, no. 10, pp. 4673–4682, Oct. 2008.
> [Public — IEEE Xplore] Analyzes rounding and truncation noise propagation through FFT stages, directly relevant to the SQNR model used in this project.
> Link: https://ieeexplore.ieee.org/document/4626107
---

## II. FPGA Architecture for FFT

[4] T. N. Nguyen, V. T. Nguyen, and V. P. Hoang, "FPGA Implementation of an Image Classifier Using Pipelined FFT Architecture," *IEEE Transactions on Very Large Scale Integration (VLSI) Systems*, vol. 33, no. 2, pp. 245-255, Feb. 2025.
> [Public – IEEE Xplore] Introduces an image classification hardware accelerator design utilizing a high-throughput pipelined FFT processor on FPGA, providing a valuable reference for optimizing pipeline stages and data path efficiency.
> Link: https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=10755115


[5] C. Aktas and S. S. S. Erdogan, "Floating-point mixed-radix FFT core generation for FPGA and comparison with GPU and CPU," in *Proceedings of the 2011 International Conference on Field-Programmable Technology (FPT)*, New Delhi, India, 2011, pp. 1-4.
> [Public – ResearchGate] Presents a comprehensive performance and resource comparison of floating-point mixed-radix FFT implementations across FPGA, GPU, and CPU platforms, highlighting the high-throughput advantages of hardware acceleration.
> Link: https://www.researchgate.net/publication/220914948_Floating-point_mixed-radix_FFT_core_generation_for_FPGA_and_comparison_with_GPU_and_CPU

[6] M. Garrido, K. K. Parhi, and P. Löfgren, "A 1 million-point FFT on a single FPGA," Linköping University, Tech. Rep., 2019.
> [Public — DiVA Portal] Demonstrates the scalability of memory-based FFT architectures on Xilinx FPGAs. Shows resource utilization trends relevant to the synthesis results in this project.
> Link: https://scispace.com/pdf/a-1-million-point-fft-on-a-single-fpga-1iuvbvbmu0.pdf

[7] Y. Jia et al., "Fixed-point FPGA implementation of the FFT accumulation method for real-time cyclostationary analysis," *ACM Transactions on Reconfigurable Technology and Systems*, vol. 15, no. 3, 2022.
> [Public — phwl.org] Presents a full fixed-point FFT implementation flow on FPGA with verification methodology similar to that used in this project (golden model + RTL co-simulation).
> Link: http://phwl.org/assets/papers/cyclo_trets22.pdf

---

## III. Applications — Radar and OFDM

[8] I. Brayda et al., "Design space exploration of FFT architectures and numerical formats for SoC-based FMCW radar signal processing," *IEEE Access*, vol. 13, 2025.
> [Public — IEEE Xplore Open Access] Explores fixed-point vs. floating-point FFT trade-offs specifically for FMCW radar, one of the target applications motivating this research.
> Link: https://ieeexplore.ieee.org/iel8/6287639/10820123/11316476.pdf

[9] J. Tian et al., "FPGA implementation of an efficient FFT processor for FMCW radar applications," *Sensors*, vol. 21, no. 19, p. 6444, 2021.
> [Public — MDPI / PubMed Central] Full fixed-point FFT implementation targeting FMCW radar on FPGA with resource utilization and timing analysis. Provides direct comparison points for the synthesis results in this project.
> Link: https://pmc.ncbi.nlm.nih.gov/articles/PMC8512539/

[10] L. Geng et al., "An FPGA-based four-channel 128k-point FFT processor suitable for spaceborne SAR," *Electronics*, vol. 10, no. 7, p. 816, 2021.
> [Public — MDPI] Large-scale FFT implementation on FPGA for SAR radar, demonstrating how BRAM and DSP resources scale with FFT size and word-length — directly relevant to the hardware results in this work.
> Link: https://www.mdpi.com/2079-9292/10/7/816

---

## IV. Block-Floating-Point and Scaling

[11] S. Uzun et al., "Finite word length effect in practical block-floating-point FFT," in *Proc. SIGNAL 2025*, 2025.
> [Public — Thinkmind.org] Discusses block-floating-point FFT as an alternative to the fixed-scale approach used here. Provides SQNR comparison between scaled fixed-point and block-floating-point — useful for the discussion section of the paper.
> Link: https://www.thinkmind.org/articles/signal_2025_2_60_60044.pdf

---

## V. Additional Related Work

[12] P. Löfgren and M. Garrido, "SFF — the single-stream FPGA-optimized feedforward FFT hardware architecture," *Journal of Signal Processing Systems*, 2015.
> [Public — d-nb.info] Proposes the single-stream FFT architecture optimized for FPGA, related to the single-butterfly memory-based design in this project.
> Link: https://d-nb.info/1164027603/34

[13] S. S. Kamath and B. Bhanu, "Improving the fast Fourier transform for space and edge computing applications with an efficient in-place method," *Computers*, vol. 4, no. 2, p. 11, 2025.
> [Public — MDPI] Recent work on in-place FFT optimization, directly related to the in-place bit-reversal and memory reuse strategy implemented in fft_top.v.
> Link: https://www.mdpi.com/2674-113X/4/2/11

[14] A. Khairy, "Accurate performance analysis of a fixed-point FFT," in *Proc. IEEE ICECS*, 2016.
> [Public — IEEE Xplore] Empirical SQNR measurement methodology for fixed-point FFT, supporting the golden model validation approach used in this project.
> Link: https://ieeexplore.ieee.org/document/7561147/

---
