#!/usr/bin/env bash
#============================================================================
# run_sim.sh  -  RTL simulation of NanoCGRA_Lite OPT (3x3 / 32B, 4-pin UART)
#============================================================================
set -u
ROOT="/workspace/iris_c3a247b9-0025-43e1-bae8-42a940fa0b63/output/nanocgra_lite_3x3_opt"
RTL="$ROOT/rtl"
TB="$ROOT/tb"
SIM="$ROOT/sim"
REP="$ROOT/reports"
mkdir -p "$SIM" "$REP"

OUT="$REP/sim_results.txt"
{
echo "================================================================"
echo " RTL SIMULATION RESULTS  -  NanoCGRA_Lite OPT (3x3 CGRA / 32B SRAM)"
echo " Interface : 4-pin UART-only (clk, rst_n, uart_rx, uart_tx)"
echo " Simulator : Icarus Verilog (iverilog -g2012)"
echo " Date      : $(date +%Y-%m-%d)"
echo " Config    : 3x3 CGRA = 9 PEs ; SRAM = 32 x 8-bit (5-bit address)"
echo "================================================================"
echo ""
} > "$OUT"

run_tb () {
  local name="$1"; shift
  local tbfile="$1"; shift
  local srcs="$@"
  echo "########################################################################" >> "$OUT"
  echo "# TESTBENCH: $name" >> "$OUT"
  echo "########################################################################" >> "$OUT"
  iverilog -g2012 -I "$RTL" -o "$SIM/${name}.vvp" "$TB/$tbfile" $srcs 2> "$SIM/${name}_compile.log"
  if [ $? -ne 0 ]; then
    echo "COMPILE ERROR:" >> "$OUT"
    cat "$SIM/${name}_compile.log" >> "$OUT"
    echo "" >> "$OUT"
    return 1
  fi
  vvp "$SIM/${name}.vvp" >> "$OUT" 2>&1
  echo "" >> "$OUT"
}

run_tb sram   sram_tb.v            "$RTL/sram.v"
run_tb pe     pe_tb.v              "$RTL/pe.v"
run_tb uart   uart_tb.v            "$RTL/uart.v"
run_tb nano_controller nano_controller_tb.v "$RTL/nano_controller.v"
run_tb nanocgra_lite   nanocgra_lite_tb.v \
       "$RTL/sram.v" "$RTL/pe.v" "$RTL/cgra.v" "$RTL/uart.v" \
       "$RTL/bus_decoder.v" "$RTL/nano_controller.v" \
       "$RTL/uart_bridge.v" "$RTL/nanocgra_lite.v"

echo "================================================================" >> "$OUT"
echo " SUMMARY" >> "$OUT"
echo "================================================================" >> "$OUT"
PASSED=$(grep -c "Result: PASSED" "$OUT")
FAILED=$(grep -c "Result: FAILED" "$OUT")
echo " Testbenches PASSED : $PASSED" >> "$OUT"
echo " Testbenches FAILED : $FAILED" >> "$OUT"
echo "================================================================" >> "$OUT"

echo "PASSED=$PASSED FAILED=$FAILED"
