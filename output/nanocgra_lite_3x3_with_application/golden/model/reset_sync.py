"""reset_sync — power-on + synchronous reset generator.

Hardware: rtl/reset_sync.v
Ports (name, dir, width):
  clk          input  1
  rst_async_n  input  1   (external async active-low reset)
  rst_n        output 1   (synchronized active-low reset)

Behaviour: on the first few clocks after power-on (or while
rst_async_n is low) the output rst_n is held low; once rst_async_n
is high and the sync chain has flushed, rst_n deasserts
synchronously.  For the golden model we model a 2-flop synchronizer.
"""

class ResetSync:
    def __init__(self, sync_depth=2):
        self.sync_depth = sync_depth
        self.shreg = [0] * sync_depth   # 0 == reset asserted

    def reset(self):
        self.shreg = [0] * self.sync_depth

    def step(self, clk, rst_async_n):
        """Advance one clock. Returns rst_n (1=not in reset)."""
        # shift on rising edge
        if clk:
            self.shreg = [1 if rst_async_n else 0] + self.shreg[:-1]
        rst_n = self.shreg[-1]
        return rst_n