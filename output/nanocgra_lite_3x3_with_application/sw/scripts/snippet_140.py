import json
# The reset_sync vec 5 mismatch: the golden model's step() shifts on clk=1, so
# when rst_async_n goes 1->0 at vec 5, the model still has the old shreg value (1)
# because the shift happens: shreg = [0] + shreg[:-1] = [0, 1], rst_n = shreg[-1] = 1.
# But the expected is 0. 
# The RTL reset_sync.v uses async reset: always @(posedge clk or negedge rst_async_n)
# so when rst_async_n goes low, rst_n goes to 0 IMMEDIATELY (async), not on next clock.
# The vector expects async behavior. The golden model is purely synchronous.
# 
# So the vector file was generated with the RTL's async behavior, not the golden model's
# synchronous behavior. The vectors are the contract.
# 
# For the TB: we drive rst_async_n, and the RTL will produce rst_n=0 immediately when
# rst_async_n=0 (async). So the TB should check rst_n combinationally/async.
# 
# The key insight: the vectors represent the EXPECTED RTL behavior, cycle by cycle.
# For reset_sync, vec 5 has rst_async_n=0 and expects rst_n=0 — the RTL produces this
# via async reset. So the TB timing must account for this.
#
# For the TB approach: I'll drive inputs, then check outputs. For async reset modules,
# the output changes immediately. For synchronous modules, the output changes on posedge clk.
#
# The safest approach: drive inputs at negedge clk, then at posedge clk check outputs.
# But for async reset, the output changes when rst_async_n changes (not on clock edge).
#
# Let me think about the TB structure that matches the vector timing:
# - The vectors are a sequence of (inputs, expected_outputs) pairs
# - Each pair represents one clock cycle
# - For the TB: set inputs, toggle clock once, check outputs
# - For async reset: the reset takes effect immediately, so we need to check after
#   the input is set but the async path fires before the clock edge
#
# Actually, the simplest approach that works for ALL modules:
# 1. Set inputs (at negedge or just before posedge)
# 2. @(posedge clk) — this triggers the sequential logic
# 3. #1 — small delay for outputs to settle
# 4. Check outputs
#
# For async reset: if rst_async_n=0, the always @(negedge rst_async_n) fires immediately
# when we set rst_async_n=0, so rst_n goes to 0 before the clock edge. Then at posedge,
# it stays 0. So checking after posedge works.
#
# But vec 5: rst_async_n goes from 1 to 0. In the TB, we set rst_async_n=0, then 
# @(posedge clk). The async reset fires when rst_async_n goes 0, setting sync0=0, sync1=0,
# rst_n=0. Then at posedge, since rst_async_n=0, the async path keeps them at 0.
# So after posedge, rst_n=0. Expected=0. Match!
#
# For the golden model, step(1, 0) does shreg=[0]+shreg[:-1]=[0,1], rst_n=shreg[-1]=1.
# That's the mismatch — the golden model is synchronous, the RTL is async.
# The VECTORS match the RTL (async), not the golden model. Good — vectors are the contract.

print("reset_sync vectors match RTL async behavior. TB will use posedge clk + check.")