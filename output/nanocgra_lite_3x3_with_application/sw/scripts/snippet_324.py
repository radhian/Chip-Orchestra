import subprocess

# Run nano_controller unit test
print("=== nano_controller_tb ===")
print(subprocess.run(['sh','-c','iverilog -g2012 -o work/nc.vvp -Irtl -s nano_controller_tb rtl/*.v tb/nano_controller_tb.* && vvp work/nc.vvp'], capture_output=True, text=True).stdout[-1000:])

# Run uart_tx unit test
print("=== uart_tx_tb ===")
print(subprocess.run(['sh','-c','iverilog -g2012 -o work/ut.vvp -Irtl -s uart_tx_tb rtl/*.v tb/uart_tx_tb.* && vvp work/ut.vvp'], capture_output=True, text=True).stdout[-1000:])