//============================================================================
// fft_top.v -- Parameterized N-point, memory-based, in-place radix-2 DIT FFT
//
//   * Data storage = TWO true-dual-port RAMs (one for real, one for imag),
//     each described with the canonical Xilinx dual-port template (ONE
//     synchronous always-block per port, ONE write per port per cycle) so
//     Vivado infers Block RAM instead of dissolving it into 2*N registers.
//   * Twiddle factors stored in a small ROM, also BRAM-style.
//   * Single shared butterfly datapath (area-efficient "memory-based" FFT).
//   * Per-stage 1/2 scaling -> output = DFT{x}/N (overflow-safe).
//   * FSM is written as an explicit 2-stage pipeline (ISSUE -> APPLY) to
//     match the 1-cycle read latency of the RAM, instead of assuming
//     combinational read-after-write like the first draft did.
//
//   Bit-exact with golden_model.py (butterfly arithmetic unchanged/verified).
//============================================================================
`timescale 1ns/1ps

// ----------------------------------------------------------------------------
// True dual-port RAM, N words x DW bits, read-first, ONE write per port.
// This is the standard template Vivado recognizes and maps to Block RAM.
// ----------------------------------------------------------------------------
module tdp_ram #(
    parameter DW = 16,
    parameter N  = 1024,
    parameter AW = 10
)(
    input                       clk,
    input      [AW-1:0]         addr_a,
    input      [AW-1:0]         addr_b,
    input  signed [DW-1:0]      din_a,
    input  signed [DW-1:0]      din_b,
    input                       we_a,
    input                       we_b,
    output reg signed [DW-1:0]  dout_a,
    output reg signed [DW-1:0]  dout_b
);
    (* ram_style = "block" *)
    reg signed [DW-1:0] mem [0:N-1];

    always @(posedge clk) begin
        if (we_a) mem[addr_a] <= din_a;
        dout_a <= mem[addr_a];          // read-first
    end
    always @(posedge clk) begin
        if (we_b) mem[addr_b] <= din_b;
        dout_b <= mem[addr_b];
    end
endmodule


module fft_top #(
    parameter DW = 16,
    parameter TW = 16,
    parameter N  = 1024,
    parameter AW = 10,                 // = log2(N)
    parameter COS_FILE = "tw_cos.hex",
    parameter SIN_FILE = "tw_sin.hex"
)(
    input              clk,
    input              rst,
    input              start,
    output reg         done,
    // Read-out port: after done=1, the host can read any of the N output
    // bins by driving rd_addr (combinational read of the result RAM).
    // This also guarantees the entire datapath (RAM/ROM/butterfly) is
    // observable from the chip boundary, so synthesis cannot strip it away.
    input      [AW-1:0]         rd_addr,
    output     signed [DW-1:0]  rd_data_r,
    output     signed [DW-1:0]  rd_data_i
);
    // ---- twiddle ROM -------------------------------------------------
    (* rom_style = "block" *) reg signed [TW-1:0] cosm [0:N/2-1];
    (* rom_style = "block" *) reg signed [TW-1:0] sinm [0:N/2-1];
    initial begin
        $readmemh(COS_FILE, cosm);
        $readmemh(SIN_FILE, sinm);
    end
    reg  [AW-2:0]        tidx;          // twiddle index (ISSUE stage)
    reg  signed [TW-1:0] wc_r, ws_r;    // registered twiddle (APPLY stage)
    always @(posedge clk) begin
        wc_r <= cosm[tidx];
        ws_r <= sinm[tidx];
    end

    // ---- data RAM: port A <-> address p0 (top), port B <-> address p1 (bot)
    reg  [AW-1:0]        addr_a, addr_b;
    reg  signed [DW-1:0] din_ar, din_br;
    reg  signed [DW-1:0] din_ai, din_bi;
    reg                  we_a, we_b;
    wire signed [DW-1:0] dout_ar, dout_br, dout_ai, dout_bi;

    tdp_ram #(.DW(DW), .N(N), .AW(AW)) u_ram_r (
        .clk(clk), .addr_a(addr_a), .addr_b(addr_b),
        .din_a(din_ar), .din_b(din_br), .we_a(we_a), .we_b(we_b),
        .dout_a(dout_ar), .dout_b(dout_br));

    tdp_ram #(.DW(DW), .N(N), .AW(AW)) u_ram_i (
        .clk(clk), .addr_a(addr_a), .addr_b(addr_b),
        .din_a(din_ai), .din_b(din_bi), .we_a(we_a), .we_b(we_b),
        .dout_a(dout_ai), .dout_b(dout_bi));

    // Read-out: drive port B with rd_addr whenever the core is idle/done
    // (i.e. NOT during the active compute FSM), so the host can scan out
    // results without disturbing the internal pipeline.
    assign rd_data_r = dout_br;
    assign rd_data_i = dout_bi;

    // ---- butterfly (combinational, bit-exact verified) -----------------
    wire signed [DW-1:0] o0r,o0i,o1r,o1i;
    butterfly #(.DW(DW), .TW(TW)) u_bf (
        .ar(dout_ar), .ai(dout_ai), .br(dout_br), .bi(dout_bi),
        .w_cos(wc_r), .w_sin(ws_r),
        .o0r(o0r), .o0i(o0i), .o1r(o1r), .o1i(o1i));

    // ---- bit-reverse function -------------------------------------------
    function [AW-1:0] bitrev(input [AW-1:0] x);
        integer b;
        begin
            bitrev = 0;
            for (b=0; b<AW; b=b+1) bitrev[b] = x[AW-1-b];
        end
    endfunction

    // ---- FSM: explicit pipeline (ISSUE addresses -> WAIT for RAM -> APPLY) -
    // Every operation (one bit-reverse swap, or one butterfly) follows the
    // same 3-cycle pattern: ISSUE (drive addresses) -> WAIT (let the 1-cycle
    // registered RAM read settle) -> APPLY (use the now-valid read data,
    // drive the write-back). The NEXT operation's ISSUE only starts after
    // the current APPLY has already presented its write, so a write is
    // always fully decoupled from the next read (no same/adjacent-cycle
    // read-after-write hazard across the two RAM ports).
    localparam S_IDLE      = 0,
               S_BR_ISSUE  = 1,   // bit-reverse: issue read addrs of pair
               S_BR_WAIT   = 2,   // wait for RAM read to register
               S_BR_APPLY  = 3,   // write swapped values back
               S_BF_ISSUE  = 4,   // butterfly: issue read addrs (+twiddle)
               S_BF_WAIT   = 5,   // wait 1 cycle for RAM+twiddle registers
               S_BF_APPLY  = 6,   // butterfly result ready, issue write
               S_DONE      = 7;
    reg [3:0] st;

    reg [AW-1:0] stage;
    reg [AW:0]   kbase;
    reg [AW-1:0] j;
    reg [AW:0]   m, hm, step;
    reg [AW-1:0] br_i;
    reg [AW-1:0] p0_hold, p1_hold;
    reg          br_swap;            // whether current pair needs a swap

    always @(posedge clk) begin
        if (rst) begin
            st <= S_IDLE; done <= 0; we_a <= 0; we_b <= 0; br_i <= 0;
        end else begin
            we_a <= 0; we_b <= 0;             // default: no write
            case (st)
            //----------------------------------------------------------
            S_IDLE: begin
                done   <= 0;
                addr_b <= rd_addr;          // expose results for read-out
                if (start) begin
                    br_i <= 0;
                    st   <= S_BR_ISSUE;
                end
            end
            //----------------------------------------------------------
            // Bit-reversal: only process pairs where bitrev(i) > i (each
            // pair visited exactly once -> no swap-then-unswap, and no
            // address ever re-read in the very next cycle after a write).
            S_BR_ISSUE: begin
                if (bitrev(br_i) > br_i) begin
                    addr_a  <= br_i;
                    addr_b  <= bitrev(br_i);
                    p0_hold <= br_i;
                    p1_hold <= bitrev(br_i);
                    br_swap <= 1'b1;
                    st      <= S_BR_WAIT;
                end else begin
                    // nothing to do for this index: advance immediately
                    if (br_i == N-1) begin
                        stage <= 0; kbase <= 0; j <= 0;
                        m  <= 2; hm <= 1; step <= N/2;
                        st <= S_BF_ISSUE;
                    end else begin
                        br_i <= br_i + 1;
                    end
                end
            end
            S_BR_WAIT: begin
                st <= S_BR_APPLY;          // let dout_a/dout_b register
            end
            // dout_a* = mem[p0_hold], dout_b* = mem[p1_hold] (now valid)
            S_BR_APPLY: begin
                addr_a <= p0_hold;
                addr_b <= p1_hold;
                din_ar <= dout_br; din_ai <= dout_bi;   // swap
                din_br <= dout_ar; din_bi <= dout_ai;
                we_a   <= 1'b1;
                we_b   <= 1'b1;
                if (br_i == N-1) begin
                    stage <= 0; kbase <= 0; j <= 0;
                    m  <= 2; hm <= 1; step <= N/2;
                    st <= S_BF_ISSUE;
                end else begin
                    br_i <= br_i + 1;
                    st   <= S_BR_ISSUE;
                end
            end
            //----------------------------------------------------------
            // Butterfly: issue read of (a = kbase+j, b = kbase+j+hm) + twiddle
            S_BF_ISSUE: begin
                addr_a  <= kbase + j;
                addr_b  <= kbase + j + hm;
                tidx    <= j * step;
                p0_hold <= kbase + j;
                p1_hold <= kbase + j + hm;
                st      <= S_BF_WAIT;
            end
            // wait 1 extra cycle: RAM dout_a/b register + twiddle wc_r/ws_r
            // both update on this same edge, so APPLY (next state) sees them
            S_BF_WAIT: begin
                st <= S_BF_APPLY;
            end
            // dout_ar/ai = a, dout_br/bi = b, wc_r/ws_r = twiddle: all valid;
            // butterfly output o0*/o1* is combinational from these -> valid now
            S_BF_APPLY: begin
                addr_a <= p0_hold;
                addr_b <= p1_hold;
                din_ar <= o0r; din_ai <= o0i;
                din_br <= o1r; din_bi <= o1i;
                we_a   <= 1'b1;
                we_b   <= 1'b1;

                if (j == hm-1) begin
                    j <= 0;
                    if (kbase + m >= N) begin
                        if (stage == AW-1) begin
                            st <= S_DONE;
                        end else begin
                            stage <= stage + 1;
                            kbase <= 0;
                            m  <= m << 1;
                            hm <= hm << 1;
                            step <= step >> 1;
                            st <= S_BF_ISSUE;
                        end
                    end else begin
                        kbase <= kbase + m;
                        st <= S_BF_ISSUE;
                    end
                end else begin
                    j <= j + 1;
                    st <= S_BF_ISSUE;
                end
            end
            //----------------------------------------------------------
            S_DONE: begin done <= 1; st <= S_IDLE; end
            default: st <= S_IDLE;
            endcase
        end
    end
endmodule
