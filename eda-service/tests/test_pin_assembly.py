from pathlib import Path
import pytest
from toolchain.pin_assembly import def_pins, stream_map

def test_def_pin_geometry_uses_declared_units(tmp_path):
    source=tmp_path/'core.def'
    source.write_text('UNITS DISTANCE MICRONS 2000 ;\nPINS 1 ;\n'
                      '- result + NET result + DIRECTION OUTPUT + PORT '
                      '+ LAYER Metal2 ( -280 -520 ) ( 280 520 ) '
                      '+ PLACED ( 80000 520 ) N ;\nEND PINS\n')
    pin=def_pins(source)['result']
    assert pin['point']==(40.0,0.26)
    assert pin['rect']==(39.86,0.0,40.14,0.52)
    assert pin['direction']=='OUTPUT'

def test_unsupported_pin_orientation_fails_instead_of_misrouting(tmp_path):
    source=tmp_path/'core.def'
    source.write_text('UNITS DISTANCE MICRONS 1000 ;\nPINS 1 ;\n'
                      '- clk + DIRECTION INPUT + LAYER Metal2 ( 0 0 ) ( 1 1 ) '
                      '+ PLACED ( 2 3 ) W ;\nEND PINS\n')
    with pytest.raises(ValueError,match='orientation'):def_pins(source)

def test_stream_map_separates_geometry_from_labels(tmp_path):
    source=tmp_path/'technology.map'
    source.write_text('Metal2 NET,SPNET,PIN,VIA 36 0\nMetal2 PIN 36 10\nVia2 VIA 38 0\nMetal3 NET 42 0\n')
    assert stream_map(source)=={'Metal2':36,'Via2':38,'Metal3':42}
