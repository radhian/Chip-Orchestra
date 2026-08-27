import subprocess
print(subprocess.run(['sh','-c','iverilog -g2012 -o work/ut.vvp -Irtl -s uart_tx_tb rtl/*.v tb/uart_tx_tb.* && vvp work/ut.vvp'], capture_output=True, text=True).stdout[-3000:])