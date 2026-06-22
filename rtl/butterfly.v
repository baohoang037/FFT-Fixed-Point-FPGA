//============================================================================
// butterfly.v  -- Parameterized radix-2 DIT butterfly with 1/2 scaling
//   t  = W_N^k * b                         (DW+1-bit complex product)
//   o0 = sat( (a + t + 1) >>> 1 )          top output   (DW bits)
//   o1 = sat( (a - t + 1) >>> 1 )          bottom output
//   After log2(N) stages -> DFT{x}/N. Bit-exact with the Python golden model.
//============================================================================
`timescale 1ns/1ps
module butterfly #(
    parameter DW = 16,
    parameter TW = 16
)(
    input  signed [DW-1:0] ar, input  signed [DW-1:0] ai,
    input  signed [DW-1:0] br, input  signed [DW-1:0] bi,
    input  signed [TW-1:0] w_cos,
    input  signed [TW-1:0] w_sin,
    output signed [DW-1:0] o0r, output signed [DW-1:0] o0i,
    output signed [DW-1:0] o1r, output signed [DW-1:0] o1i
);
    wire signed [DW:0] tr, ti;                    // DW+1-bit twiddle product
    wire signed [TW-1:0] ci = -w_sin;             // ci = -sin

    complex_mult #(.DW(DW), .TW(TW)) u_cm (
        .br(br), .bi(bi), .cr(w_cos), .ci(ci), .tr(tr), .ti(ti)
    );

    // sign-extend a to DW+1 then add/sub the (DW+1)-bit t, +1 rounding, >>>1
    wire signed [DW+1:0] sum_r = $signed(ar) + tr + 1;
    wire signed [DW+1:0] sum_i = $signed(ai) + ti + 1;
    wire signed [DW+1:0] dif_r = $signed(ar) - tr + 1;
    wire signed [DW+1:0] dif_i = $signed(ai) - ti + 1;

    wire signed [DW+1:0] s0r = sum_r >>> 1;
    wire signed [DW+1:0] s0i = sum_i >>> 1;
    wire signed [DW+1:0] s1r = dif_r >>> 1;
    wire signed [DW+1:0] s1i = dif_i >>> 1;

    localparam signed [DW+1:0] MAXV =  (1 <<< (DW-1)) - 1;
    localparam signed [DW+1:0] MINV = -(1 <<< (DW-1));
    function signed [DW-1:0] satf(input signed [DW+1:0] v);
        satf = (v > MAXV) ? MAXV[DW-1:0] : (v < MINV) ? MINV[DW-1:0] : v[DW-1:0];
    endfunction

    assign o0r = satf(s0r); assign o0i = satf(s0i);
    assign o1r = satf(s1r); assign o1i = satf(s1i);
endmodule
