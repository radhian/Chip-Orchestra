import json, os, sys, random
sys.path.insert(0, 'golden')
from model.params import (IMG_W, IMG_H, OUT_W, OUT_H, CLK_FREQ, BAUD_RATE,
                          ADDR_SRAM_BASE, ADDR_UART_TXDATA, ADDR_UART_RXDATA,
                          ADDR_UART_STATUS, ADDR_UART_CTRL, ADDR_CGRA_CFG_BASE,
                          ADDR_CGRA_OPA, ADDR_CGRA_OPB, ADDR_CGRA_RES,
                          ADDR_START, ADDR_STATUS, SOBEL_GX, SOBEL_GY)
from model.sobel_core import sobel_compute
from model.pe import PE
from model.cgra_3x3 import CGRA3x3, CFG_GX, CFG_GY
from model.line_buffer import LineBuffer
from model.window_3x3 import Window3x3
from model.sram_32b import SRAM32B
from model.mmio_bus import MMIOBus
from model.nano_controller import NanoController
from model.reset_sync import ResetSync
from model.uart_rx import UartRx
from model.uart_tx import UartTx
from model.baud_gen import BaudGen
from model.top import sobel_stream

DIV = CLK_FREQ // BAUD_RATE
os.makedirs('golden/vectors', exist_ok=True)

def wj(name, obj):
    with open(os.path.join('golden/vectors', name), 'w') as f:
        json.dump(obj, f, indent=2)

# ---------- reset_sync ----------
rs = ResetSync(sync_depth=2); rs.reset()
vecs = []
for c in range(5):
    r = rs.step(1, 1)
    vecs.append({"inputs":{"clk":1,"rst_async_n":1}, "expected":{"rst_n":r}})
rs.reset()
for c in range(5):
    r = rs.step(1, 0)
    vecs.append({"inputs":{"clk":1,"rst_async_n":0}, "expected":{"rst_n":r}})
rs.reset()
for c in range(3): rs.step(1, 0)
for c in range(4):
    r = rs.step(1, 1)
    vecs.append({"inputs":{"clk":1,"rst_async_n":1}, "expected":{"rst_n":r}})
wj('reset_sync.json', {"module":"reset_sync",
  "ports":{"inputs":[["clk",1],["rst_async_n",1]],"outputs":[["rst_n",1]]},
  "vectors":vecs})

# ---------- baud_gen ----------
bg = BaudGen(); bg.reset()
vecs=[]
for c in range(DIV*3+2):
    t = bg.step(1,1)
    vecs.append({"inputs":{"clk":1,"rst_n":1},"expected":{"baud_tick":t}})
bg.reset()
for c in range(5):
    t = bg.step(1,0)
    vecs.append({"inputs":{"clk":1,"rst_n":0},"expected":{"baud_tick":t}})
wj('baud_gen.json', {"module":"baud_gen",
  "ports":{"inputs":[["clk",1],["rst_n",1]],"outputs":[["baud_tick",1]]},
  "vectors":vecs})

# ---------- pe ----------
vecs=[]
cases = [
  (PE.PASS, 0x53, 0),(PE.ZERO, 0xFF, 0),(PE.SHL1, 0x10, 0),(PE.SHL1, 0x80, 0),
  (PE.NEG, 0x05, 0),(PE.NEG_SHL1, 0x03, 0),(PE.ABS, 0xFB, 0),(PE.MUL, 0x10, 0x02),(PE.ADD, 0x10, 0x05),
]
for cfg,opa,opb in cases:
    pe=PE(); pe.reset()
    r,_=pe.step(1,1,cfg,opa,opb)
    vecs.append({"inputs":{"clk":1,"rst_n":1,"cfg":cfg,"opa":opa,"opb":opb},
                 "expected":{"result":r,"cout":r}})
pe=PE(); pe.reset()
r,_=pe.step(1,0,PE.PASS,0x42,0)
vecs.append({"inputs":{"clk":1,"rst_n":0,"cfg":PE.PASS,"opa":0x42,"opb":0},
             "expected":{"result":r,"cout":r}})
wj('pe.json', {"module":"pe",
  "ports":{"inputs":[["clk",1],["rst_n",1],["cfg",3],["opa",8],["opb",8]],
           "outputs":[["result",8],["cout",8]]},
  "vectors":vecs})

# ---------- sobel_core ----------
vecs=[]
test_wins = [[100]*9,[0,0,255,0,0,255,0,0,255],[0,0,0,0,0,0,255,255,255],
  [10,20,30,40,50,60,70,80,90],[5,10,15,10,15,20,15,20,25]]
random.seed(11)
for _ in range(15):
    test_wins.append([random.randint(0,255) for _ in range(9)])
for w in test_wins:
    gx,gy,o = sobel_compute(w)
    vecs.append({"inputs":{"win":w},"expected":{"sobel_out":o}})
wj('sobel_core.json', {"module":"sobel_core",
  "ports":{"inputs":[["win",72]],"outputs":[["sobel_out",8]]},
  "vectors":vecs})

# ---------- cgra_3x3 ----------
vecs=[]
random.seed(13)
cgra_wins = [[100]*9,[0,0,255,0,0,255,0,0,255],[0,0,0,0,0,0,255,255,255]]
for _ in range(12):
    cgra_wins.append([random.randint(0,255) for _ in range(9)])
for w in cgra_wins:
    c=CGRA3x3(); c.reset()
    o,d = c.step(1,1,w,1)
    vecs.append({"inputs":{"clk":1,"rst_n":1,"win":w,"start":1},
                 "expected":{"sobel_out":o,"done":d}})
c=CGRA3x3(); c.reset()
o,d=c.step(1,0,[0]*9,0)
vecs.append({"inputs":{"clk":1,"rst_n":0,"win":[0]*9,"start":0},
             "expected":{"sobel_out":o,"done":d}})
wj('cgra_3x3.json', {"module":"cgra_3x3",
  "ports":{"inputs":[["clk",1],["rst_n",1],["win",72],["start",1]],
           "outputs":[["sobel_out",8],["done",1]]},
  "vectors":vecs})

# ---------- line_buffer ----------
vecs=[]
lb=LineBuffer(); lb.reset()
for i in range(IMG_W+5):
    lb.step(1,1,1,i)
    vecs.append({"inputs":{"clk":1,"rst_n":1,"shift_en":1,"pixel_in":i&0xFF},
                 "expected":{"row_out":list(lb.row)}})
lb2=LineBuffer(); lb2.reset()
lb2.step(1,1,1,42); lb2.step(1,1,0,99)
vecs.append({"inputs":{"clk":1,"rst_n":1,"shift_en":0,"pixel_in":99},
             "expected":{"row_out":list(lb2.row)}})
lb3=LineBuffer(); lb3.row=[0xFF]*IMG_W
lb3.step(1,0,0,0)
vecs.append({"inputs":{"clk":1,"rst_n":0,"shift_en":0,"pixel_in":0},
             "expected":{"row_out":list(lb3.row)}})
wj('line_buffer.json', {"module":"line_buffer",
  "ports":{"inputs":[["clk",1],["rst_n",1],["shift_en",1],["pixel_in",8]],
           "outputs":[["row_out",256]]},
  "vectors":vecs})

# ---------- window_3x3 ----------
vecs=[]
w=Window3x3(); w.reset()
for row in range(3):
    for col in range(3):
        pixel=row*10+col
        lb0=(row-2)*10+col if row>=2 else 0
        lb1=(row-1)*10+col if row>=1 else 0
        win,valid=w.step(1,1,1,pixel,lb0&0xFF,lb1&0xFF,col,row)
        vecs.append({"inputs":{"clk":1,"rst_n":1,"shift_en":1,"pixel_in":pixel,
                               "lb0_data":lb0&0xFF,"lb1_data":lb1&0xFF,
                               "col_cnt":col,"row_cnt":row},
                     "expected":{"win":list(win),"window_valid":valid}})
w2=Window3x3(); w2.reset()
for row in range(2):
    for col in range(3):
        pixel=row*10+col
        lb1=(row-1)*10+col if row>=1 else 0
        win,valid=w2.step(1,1,1,pixel,0,lb1&0xFF,col,row)
        vecs.append({"inputs":{"clk":1,"rst_n":1,"shift_en":1,"pixel_in":pixel,
                               "lb0_data":0,"lb1_data":lb1&0xFF,
                               "col_cnt":col,"row_cnt":row},
                     "expected":{"win":list(win),"window_valid":valid}})
wj('window_3x3.json', {"module":"window_3x3",
  "ports":{"inputs":[["clk",1],["rst_n",1],["shift_en",1],["pixel_in",8],
                     ["lb0_data",8],["lb1_data",8],["col_cnt",6],["row_cnt",6]],
           "outputs":[["win",72],["window_valid",1]]},
  "vectors":vecs})

# ---------- sram_32b ----------
vecs=[]
s=SRAM32B(); s.reset()
for a in range(32):
    s.step(1,1,a,1,(a*2)&0xFF)
    vecs.append({"inputs":{"clk":1,"rst_n":1,"addr":a,"wr_en":1,"data_in":(a*2)&0xFF},
                 "expected":{"data_out":s.data_out}})
for a in range(32):
    s.step(1,1,a,0,0)
    vecs.append({"inputs":{"clk":1,"rst_n":1,"addr":a,"wr_en":0,"data_in":0},
                 "expected":{"data_out":s.data_out}})
s2=SRAM32B(); s2.mem=[0xFF]*32
s2.step(1,0,0,0,0)
vecs.append({"inputs":{"clk":1,"rst_n":0,"addr":0,"wr_en":0,"data_in":0},
             "expected":{"data_out":s2.data_out}})
wj('sram_32b.json', {"module":"sram_32b",
  "ports":{"inputs":[["clk",1],["rst_n",1],["addr",5],["wr_en",1],["data_in",8]],
           "outputs":[["data_out",8]]},
  "vectors":vecs})

# ---------- mmio_bus ----------
vecs=[]
bus_cases = [
  (0x10,0,1,0,0x42,0x42,0,0),
  (ADDR_UART_TXDATA,0,1,0,0,0,0x55,0),
  (ADDR_CGRA_CFG_BASE,0,1,0,0,0,0,0x77),
  (ADDR_START,1,0,0x01,0,0,0,0),
  (0x05,1,0,0xAB,0,0,0,0),
]
for addr,wr,rd,wdata,sr,ur,cr in bus_cases:
    b=MMIOBus(); b.reset()
    o=b.step(1,1,addr,wr,rd,wdata,sr,ur,cr)
    vecs.append({"inputs":{"clk":1,"rst_n":1,"mst_addr":addr,"mst_wr":wr,"mst_rd":rd,
                           "mst_wdata":wdata,"sram_rdata":sr,"uart_rdata":ur,"cgra_rdata":cr},
                 "expected":o})
b=MMIOBus(); b.reset()
o=b.step(1,0,0,0,0,0,0,0,0)
vecs.append({"inputs":{"clk":1,"rst_n":0,"mst_addr":0,"mst_wr":0,"mst_rd":0,
                       "mst_wdata":0,"sram_rdata":0,"uart_rdata":0,"cgra_rdata":0},
             "expected":o})
wj('mmio_bus.json', {"module":"mmio_bus",
  "ports":{"inputs":[["clk",1],["rst_n",1],["mst_addr",8],["mst_wr",1],["mst_rd",1],
                     ["mst_wdata",8],["sram_rdata",8],["uart_rdata",8],["cgra_rdata",8]],
           "outputs":[["mst_rdata",8],["sram_sel",1],["uart_sel",1],["cgra_sel",1],
                      ["sram_addr",5],["sram_wr_en",1],["sram_wdata",8]]},
  "vectors":vecs})

# ---------- nano_controller ----------
vecs=[]
c=NanoController(); c.reset()
o=c.step(1,1,0x42,1,0,0,0)
vecs.append({"inputs":{"clk":1,"rst_n":1,"rx_byte":0x42,"rx_valid":1,"tx_done":0,"cgra_done":0,"sobel_out":0},"expected":o})
for i in range(5):
    o=c.step(1,1,i,1,0,0,0)
    vecs.append({"inputs":{"clk":1,"rst_n":1,"rx_byte":i,"rx_valid":1,"tx_done":0,"cgra_done":0,"sobel_out":0},"expected":o})
c2=NanoController(); c2.reset()
o=c2.step(1,0,0,0,0,0,0)
vecs.append({"inputs":{"clk":1,"rst_n":0,"rx_byte":0,"rx_valid":0,"tx_done":0,"cgra_done":0,"sobel_out":0},"expected":o})
wj('nano_controller.json', {"module":"nano_controller",
  "ports":{"inputs":[["clk",1],["rst_n",1],["rx_byte",8],["rx_valid",1],["tx_done",1],["cgra_done",1],["sobel_out",8]],
           "outputs":[["bus_addr",8],["bus_wr",1],["bus_rd",1],["bus_wdata",8],["pixel_in",8],["pixel_shift",1],["col_cnt",6],["row_cnt",6],["start_cgra",1],["tx_start",1],["tx_data",8],["status",8]]},
  "vectors":vecs})

# ---------- uart_rx ----------
vecs=[]
for byte in [0xA5,0x00,0xFF,0x3C]:
    rx=UartRx(); rx.reset()
    seq=[]
    for _ in range(DIV): seq.append(0)
    for b in range(8):
        bit=(byte>>b)&1
        for _ in range(DIV): seq.append(bit)
    for _ in range(DIV): seq.append(1)
    for rxin in seq:
        _,v=rx.step(1,1,rxin)
        vecs.append({"inputs":{"clk":1,"rst_n":1,"rx_in":rxin},
                     "expected":{"rx_valid":v}})
    vecs.append({"inputs":{"clk":1,"rst_n":1,"rx_in":1},
                 "expected":{"rx_byte":rx.rx_byte}})
rx=UartRx(); rx.reset()
_,v=rx.step(1,0,1)
vecs.append({"inputs":{"clk":1,"rst_n":0,"rx_in":1},"expected":{"rx_valid":v}})
wj('uart_rx.json', {"module":"uart_rx",
  "ports":{"inputs":[["clk",1],["rst_n",1],["rx_in",1]],
           "outputs":[["rx_byte",8],["rx_valid",1]]},
  "vectors":vecs})

# ---------- uart_tx ----------
vecs=[]
for byte in [0x3C,0xFF,0xA5,0x00]:
    tx=UartTx(); tx.reset()
    tx.step(1,1,0,0); tx.step(1,1,0,0); tx.step(1,1,1,byte)
    for _ in range(DIV*12+5):
        out,done=tx.step(1,1,0,0)
        vecs.append({"inputs":{"clk":1,"rst_n":1,"tx_start":0,"data_in":0},
                     "expected":{"tx_out":out,"tx_done":done}})
tx=UartTx(); tx.reset()
out,done=tx.step(1,0,0,0)
vecs.append({"inputs":{"clk":1,"rst_n":0,"tx_start":0,"data_in":0},
             "expected":{"tx_out":out,"tx_done":done}})
wj('uart_tx.json', {"module":"uart_tx",
  "ports":{"inputs":[["clk",1],["rst_n",1],["tx_start",1],["data_in",8]],
           "outputs":[["tx_out",1],["tx_done",1]]},
  "vectors":vecs})

# ---------- top ----------
vecs=[]
with open('context/chip_input_grid.json') as f:
    grid=json.load(f)
flat=[p for row in grid['pixels'] for p in row]
out=sobel_stream(flat)
vecs.append({"inputs":{"pixels":flat}, "expected":{"sobel_out_stream":out}})
wj('nano_cgra_3x3_sobel_accelerator_v4.json', {"module":"nano_cgra_3x3_sobel_accelerator_v4",
  "ports":{"inputs":[["clk",1],["rst_n",1],["data_i",1]],
           "outputs":[["data_o",1]]},
  "vectors":vecs})

print("All vector files written:")
for fn in sorted(os.listdir('golden/vectors')):
    print(" ", fn, os.path.getsize(os.path.join('golden/vectors',fn)), "bytes")