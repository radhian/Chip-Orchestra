# Memory Map

| Base Address | Size | Peripheral |
|--------------|------|------------|
|0x0000_0000|64 KB|SRAM|
|0x0001_0000|4 KB|CGRA|
|0x0002_0000|4 KB|UART|
|0x0003_0000|4 KB|GPIO|
|0x0004_0000|4 KB|Timer|

Each peripheral occupies a separate address region.

Address decoding currently uses the upper 16 address bits.