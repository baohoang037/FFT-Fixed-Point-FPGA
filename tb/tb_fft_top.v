//============================================================================
// tb_fft_top.v -- End-to-end check: full 1024-pt fixed-point FFT vs golden.
//   Loads a quantized input vector, runs fft_top, compares every bin against
//   the golden expected output (exp_*_real/imag_hex) produced by the model.
//============================================================================
`timescale 1ns/1ps
module tb_fft_top;
    parameter DW=16, TW=16; localparam N=1024, AW=10;
    reg clk=0, rst=1, start=0; wire done;
    always #5 clk = ~clk;

    fft_top #(.DW(DW),.TW(TW),.N(N),.AW(AW),
              .COS_FILE("tw_cos.hex"),.SIN_FILE("tw_sin.hex")) dut
        (.clk(clk),.rst(rst),.start(start),.done(done),
         .rd_addr({AW{1'b0}}), .rd_data_r(), .rd_data_i());

    reg [DW-1:0] in_r [0:N-1], in_i [0:N-1];
    reg [DW-1:0] exp_r[0:N-1], exp_i[0:N-1];
    integer i, errors, maxerr; integer dr, di;

    initial begin
        $readmemh("in_real.hex", in_r);
        $readmemh("in_imag.hex", in_i);
        $readmemh("exp_real.hex", exp_r);
        $readmemh("exp_imag.hex", exp_i);
        // preload working RAM (natural order; DUT does bit-reversal)
        for (i=0;i<N;i=i+1) begin
            dut.u_ram_r.mem[i] = $signed(in_r[i]);
            dut.u_ram_i.mem[i] = $signed(in_i[i]);
        end
        @(negedge clk); rst = 0;
        @(negedge clk); start = 1;
        @(negedge clk); start = 0;
        wait(done);
        @(posedge clk);

        errors=0; maxerr=0;
        for (i=0;i<N;i=i+1) begin
            dr = dut.u_ram_r.mem[i] - $signed(exp_r[i]);
            di = dut.u_ram_i.mem[i] - $signed(exp_i[i]);
            if (dr!=0 || di!=0) begin
                errors = errors + 1;
                if (dr<0) dr=-dr; if (di<0) di=-di;
                if (dr>maxerr) maxerr=dr;
                if (di>maxerr) maxerr=di;
                if (errors<=5)
                  $display("  bin %0d: got(%0d,%0d) exp(%0d,%0d)", i,
                    dut.u_ram_r.mem[i],dut.u_ram_i.mem[i],$signed(exp_r[i]),$signed(exp_i[i]));
            end
        end
        $display("====================================================");
        if (errors==0)
            $display("  FFT_TOP PASS: all %0d bins bit-exact vs golden", N);
        else
            $display("  FFT_TOP: %0d/%0d bins differ (max |err| LSB = %0d)",
                     errors, N, maxerr);
        $display("====================================================");
        $finish;
    end
endmodule
