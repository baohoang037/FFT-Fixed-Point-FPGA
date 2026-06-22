"""Generate bit-exact butterfly test vectors that mirror the golden-model
integer arithmetic, so the Verilog butterfly can be checked against them."""
import numpy as np, os, sys
sys.path.insert(0, os.path.dirname(__file__))

W   = 16          # data word length
TW  = 16          # twiddle word length
N   = 1024
FT  = TW - 1      # twiddle frac bits
HALF = 1 << (FT - 1)   # round half-up for the multiply
OUT = os.path.join(os.path.dirname(__file__), "..", "tb", "bf_vectors.txt")

def sat(v, w):
    hi = (1 << (w-1)) - 1; lo = -(1 << (w-1))
    return max(min(v, hi), lo)

rng = np.random.default_rng(7)
k = np.arange(N//2)
cos = np.clip(np.round(np.cos(2*np.pi*k/N)*(1<<FT)), -(1<<(TW-1)), (1<<(TW-1))-1).astype(int)
sin = np.clip(np.round(np.sin(2*np.pi*k/N)*(1<<FT)), -(1<<(TW-1)), (1<<(TW-1))-1).astype(int)

lines = []
NTEST = 200
for _ in range(NTEST):
    ur = int(rng.integers(-(1<<(W-1)), 1<<(W-1)))
    ui = int(rng.integers(-(1<<(W-1)), 1<<(W-1)))
    br = int(rng.integers(-(1<<(W-1)), 1<<(W-1)))
    bi = int(rng.integers(-(1<<(W-1)), 1<<(W-1)))
    idx = int(rng.integers(0, N//2))
    cr = int(cos[idx]); ci = -int(sin[idx])        # W = cos - j sin

    tr = (cr*br - ci*bi + HALF) >> FT
    ti = (cr*bi + ci*br + HALF) >> FT
    o0r = sat((ur + tr + 1) >> 1, W)
    o0i = sat((ui + ti + 1) >> 1, W)
    o1r = sat((ur - tr + 1) >> 1, W)
    o1i = sat((ui - ti + 1) >> 1, W)

    def h(v, w):
        return format(v & ((1<<w)-1), f"0{(w+3)//4}X")
    lines.append(" ".join([h(ur,W),h(ui,W),h(br,W),h(bi,W),
                           h(cos[idx],TW),h(sin[idx],TW),
                           h(o0r,W),h(o0i,W),h(o1r,W),h(o1i,W)]))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
with open(OUT, "w") as f:
    f.write(f"// W={W} TW={TW}  fields: ur ui br bi cos sin | o0r o0i o1r o1i\n")
    f.write("\n".join(lines) + "\n")
print(f"wrote {NTEST} butterfly vectors -> {OUT}")
