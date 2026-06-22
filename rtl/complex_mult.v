//============================================================================
// complex_mult.v  -- Parameterized fixed-point complex multiplier
//   t = W_tw * b , W_tw = (cr + j*ci) = (cos - j*sin) , b = (br + j*bi)
//   Data Q1.(DW-1), twiddle Q1.(TW-1). Result rounded to Q2.(DW-1): ONE extra
//   integer bit (output is DW+1 bits, NO intermediate saturation) because for a
//   complex b with |b|->sqrt(2), |t| can exceed 1.0. The final saturation is
//   done in the butterfly after the 1/2 scaling. Bit-exact with golden model.
//============================================================================
`timescale 1ns/1ps
module complex_mult #(
    parameter DW = 16,
    parameter TW = 16
)(
    input  signed [DW-1:0] br,
    input  signed [DW-1:0] bi,
    input  signed [TW-1:0] cr,   //  cos
    input  signed [TW-1:0] ci,   // -sin
    output signed [DW:0]   tr,   // DW+1 bits, Q2.(DW-1)
    output signed [DW:0]   ti
);
    localparam FT   = TW - 1;
    localparam HALF = (1 <<< (FT-1));            // round half-up

    wire signed [DW+TW+1:0] acc_r = cr*br - ci*bi + HALF;
    wire signed [DW+TW+1:0] acc_i = cr*bi + ci*br + HALF;

    wire signed [DW+TW+1:0] sr = acc_r >>> FT;   // arithmetic (floor) shift
    wire signed [DW+TW+1:0] si = acc_i >>> FT;

    assign tr = sr[DW:0];                         // truncate to DW+1 bits (no sat)
    assign ti = si[DW:0];
endmodule
