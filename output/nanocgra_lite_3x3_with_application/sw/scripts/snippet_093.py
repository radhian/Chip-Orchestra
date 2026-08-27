import os
for f in ['rtl/sobel_input.mem','rtl/sobel_golden.mem']:
    with open(f) as fh:
        lines=[l.strip() for l in fh if l.strip()]
    print(f, len(lines), 'first5', lines[:5], 'last5', lines[-5:])
    # validate hex
    bad=[l for l in lines if not all(c in '0123456789abcdefABCDEF' for c in l)]
    print('  bad hex:', bad[:5], 'count', len(bad))