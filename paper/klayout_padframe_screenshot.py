import pya
import os

gds = os.environ["CHIP_GDS"]
image = os.environ["CHIP_IMAGE"]
window = pya.Application.instance().main_window()
window.load_layout(gds, 0)
view = window.current_view()
view.add_missing_layers()
view.max_hier()
view.zoom_fit()
view.set_config("background-color", "#ffffff")
view.set_config("grid-visible", "false")
view.set_config("text-visible", "false")
view.save_image(image, 2200, 2200)
pya.Application.instance().exit(0)
