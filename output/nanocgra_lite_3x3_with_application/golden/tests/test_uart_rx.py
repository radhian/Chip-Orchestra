"""Test uart_rx — UART receiver."""
from model.uart_rx import UartRx
from model.params import CLK_FREQ, BAUD_RATE

DIV = CLK_FREQ // BAUD_RATE

def send_byte(rx, byte):
    """Drive a UART byte through the rx model. Returns list of rx_valid pulses."""
    valids = []
    # start bit
    for _ in range(DIV):
        _, v = rx.step(1, 1, 0)
        valids.append(v)
    # 8 data bits LSB first
    for b in range(8):
        bit = (byte >> b) & 1
        for _ in range(DIV):
            _, v = rx.step(1, 1, bit)
            valids.append(v)
    # stop bit
    for _ in range(DIV):
        _, v = rx.step(1, 1, 1)
        valids.append(v)
    return valids

def test_receive_0xA5():
    rx = UartRx()
    rx.reset()
    valids = send_byte(rx, 0xA5)
    assert sum(valids) == 1
    assert rx.rx_byte == 0xA5

def test_receive_0x00():
    rx = UartRx()
    rx.reset()
    valids = send_byte(rx, 0x00)
    assert sum(valids) == 1
    assert rx.rx_byte == 0x00

def test_receive_0xFF():
    rx = UartRx()
    rx.reset()
    valids = send_byte(rx, 0xFF)
    assert sum(valids) == 1
    assert rx.rx_byte == 0xFF