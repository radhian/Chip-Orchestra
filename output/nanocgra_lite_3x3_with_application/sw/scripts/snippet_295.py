import json, pathlib
rtl = sorted(p.stem for p in pathlib.Path("rtl").glob("*.v"))
js = json.loads(pathlib.Path("golden/module_math.json").read_text())
names = [m["name"] for m in js["modules"]]
print("rtl .v files:", rtl)
print("json modules:", names)
print("missing:", set(rtl) - set(names))
print("extra:", set(names) - set(rtl))
print("valid JSON: True, modules:", len(names))