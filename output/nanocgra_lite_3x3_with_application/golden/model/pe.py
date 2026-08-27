"""pe — single Processing Element (8-bit ALU/MAC).

Hardware: rtl/pe.v
Ports (name, dir, width):
  clk      input  1
  rst_n    input  1
  cfg      input  3    (operation select)
  opa      input  8    (operand A: window pixel)
  opb      input  8    (operand B: kernel weight, signed via two's comp)
  result   output 8    (combinational result)
  cout     output 8    (carry/chain output to neighbour)

cfg encodings:
  0 : pass opa            (result = opa)
  1 : multiply opa*opb    (result = opa*opb, low 8 bits)  [weight MAC]
  2 : add  opa + opb      (result = opa + opb)
  3 : shift-left-1 opa    (result = opa << 1)  [weight = +2]
  4 : negate opa          (result = -opa)      [weight = -1]
  5 : shift-left-1 + neg  (result = -(opa<<1)) [weight = -2]
  6 : pass 0              (result = 0)         [weight = 0]
  7 : abs opa             (result = |opa|)

For Sobel, each PE is configured with the weight applied to its window
pixel.  Because weights are 0, +/-1, +/-2 the PE uses shifts/adds, not
a general multiplier (cfg 3/4/5 implement the power-of-two cases).
"""

from .params import u8, s8

class PE:
    # cfg encodings
    PASS   = 0
    MUL    = 1
    ADD    = 2
    SHL1   = 3   # +2
    NEG    = 4   # -1
    NEG_SHL1 = 5 # -2
    ZERO   = 6
    ABS    = 7

    def __init__(self):
        self.result = 0
        self.cout = 0

    def reset(self):
        self.result = 0
        self.cout = 0

    def step(self, clk, rst_n, cfg, opa, opb):
        if not rst_n:
            self.reset()
            return self.result, self.cout
        a = int(opa) & 0xFF
        b = s8(opb)  # signed weight
        cfg = int(cfg) & 0x7
        if cfg == self.PASS:
            r = a
        elif cfg == self.MUL:
            r = (a * b) & 0xFF
        elif cfg == self.ADD:
            r = (a + b) & 0xFF
        elif cfg == self.SHL1:
            r = (a << 1) & 0xFF
        elif cfg == self.NEG:
            r = (-a) & 0xFF
        elif cfg == self.NEG_SHL1:
            r = (-(a << 1)) & 0xFF
        elif cfg == self.ZERO:
            r = 0
        elif cfg == self.ABS:
            r = abs(s8(a)) & 0xFF
        else:
            r = 0
        self.result = r & 0xFF
        self.cout = r & 0xFF
        return self.result, self.cout