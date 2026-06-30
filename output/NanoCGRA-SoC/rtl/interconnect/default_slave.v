`timescale 1ns/1ps

module default_slave
(
    output wire [31:0] rdata,
    output wire ready,
    output wire error
);

assign rdata = 32'hDEAD_BEEF;

assign ready = 1'b1;

assign error = 1'b1;

endmodule