"""Test uart_tx — UART transmitter."""
from model.uart_tx import UartTx
from model.params import CLK_FREQ, BAUD_RATE

DIV = CLK_FREQ // BAUD_RATE

def transmit(tx, byte):
    """Transmit a byte, capture the serial waveform.

    Returns (bits, done_pulses) where *bits* is one sample per CLOCK
    for the full frame duration and *done_pulses* is the tx_done flag
    per clock.  The caller samples bit k at the midpoint of its bit
    period: bits[first_zero + k*DIV + DIV//2].
    """
    tx.step(1, 1, 1, 0)          # idle
    tx.step(1, 1, 1, 0)          # idle
    tx.step(1, 1, 1, byte)       # pulse tx_start (latched by model)
    bits = []
    dones = []
    for _ in range(DIV * 12 + 5):
        out, done = tx.step(1, 1, 0, 0)
        bits.append(out)
        dones.append(done)
    return bits, dones

def _sample_bits(bits):
    """Sample the 10-bit UART frame at the midpoint of each bit period."""
    first_zero = next(i for i, b in enumerate(bits) if b == 0)
    return [bits[first_zero + k * DIV + DIV // 2] for k in range(10)]

def test_tx_idle_high():
    tx = UartTx()
    tx.reset()
    out, _ = tx.step(1, 1, 0, 0)
    assert out == 1

def test_transmit_0x3C():
    tx = UartTx()
    tx.reset()
    bits, dones = transmit(tx, 0x3C)
    assert sum(dones) == 1
    frame = _sample_bits(bits)
    # start bit should be 0
    assert frame[0] == 0
    # reconstruct byte from data bits (frame[1..8], LSB first)
    val = 0
    for b in range(8):
        val |= frame[1 + b] << b
    assert val == 0x3C
    # stop bit should be 1
    assert frame[9] == 1

def test_transmit_0xFF():
    tx = UartTx()
    tx.reset()
    bits, dones = transmit(tx, 0xFF)
    assert sum(dones) == 1
    frame = _sample_bits(bits)
    assert frame[0] == 0  # start
    for b in range(8):
        assert frame[1 + b] == 1
    assert frame[9] == 1  # stop