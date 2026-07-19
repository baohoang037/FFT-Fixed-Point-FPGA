//============================================================================
// tb_butterfly.v -- Self-checking testbench for the radix-2 butterfly.
//   Reads bf_vectors.txt (produced by gen_bf_vectors.py with the SAME integer
//   arithmetic as the golden model) and verifies the RTL is bit-exact.
//============================================================================
`timescale 1ns/1ps
module tb_butterfly;
    localparam DW = 16, TW = 16, NVEC = 200;

    reg  signed [DW-1:0] ar, ai, br, bi;
    reg  signed [TW-1:0] w_cos, w_sin;
    wire signed [DW-1:0] o0r, o0i, o1r, o1i;

    // golden fields read from file
    reg  [DW-1:0]  g_o0r,g_o0i,g_o1r,g_o1i;
    
    reg  [DW-1:0] mem [0:NVEC*10-1];

    integer i, base, errors;

    butterfly #(.DW(DW), .TW(TW)) dut (
        .ar(ar), .ai(ai), .br(br), .bi(bi),
        .w_cos(w_cos), .w_sin(w_sin),
        .o0r(o0r), .o0i(o0i), .o1r(o1r), .o1i(o1i)
    );

    initial begin
        $readmemh("bf_vectors.txt", mem);
        errors = 0;
        for (i = 0; i < NVEC; i = i + 1) begin
            base = i*10;
            ar = mem[base+0]; ai = mem[base+1];
            br = mem[base+2]; bi = mem[base+3];
            w_cos = mem[base+4]; w_sin = mem[base+5];
            g_o0r = mem[base+6]; g_o0i = mem[base+7];
            g_o1r = mem[base+8]; g_o1i = mem[base+9];
            #1;
            if (o0r !== $signed(g_o0r) || o0i !== $signed(g_o0i) ||
                o1r !== $signed(g_o1r) || o1i !== $signed(g_o1i)) begin
                errors = errors + 1;
                if (errors <= 5)
                  $display("MISMATCH vec %0d: got o0=(%0d,%0d) o1=(%0d,%0d)  exp o0=(%0d,%0d) o1=(%0d,%0d)",
                     i, o0r,o0i,o1r,o1i,
                     $signed(g_o0r),$signed(g_o0i),$signed(g_o1r),$signed(g_o1i));
            end
        end
        $display("----------------------------------------------------");
        if (errors == 0)
            $display("  BUTTERFLY PASS: all %0d vectors bit-exact vs golden", NVEC);
        else
            $display("  BUTTERFLY FAIL: %0d / %0d mismatches", errors, NVEC);
        $display("----------------------------------------------------");
        $finish;
    end
endmodule
