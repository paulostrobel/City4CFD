"""
ParaView script — isometric view of ground + building wall patches only.

Run:
    DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 pvbatch pv_walls.py
"""
import os
from paraview.simple import (
    OpenFOAMReader,
    Calculator,
    ExtractBlock,
    MergeBlocks,
    GetColorTransferFunction,
    GetScalarBar,
    ColorBy,
    Show, Hide,
    CreateRenderView,
    CreateLayout,
    AssignViewToLayout,
    RenderAllViews,
    ResetCamera,
    SaveScreenshot,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_DIR   = os.path.join(SCRIPT_DIR, "openfoam")
FOAM_FILE  = os.path.join(CASE_DIR, "Brasilia.foam")

if not os.path.exists(FOAM_FILE):
    open(FOAM_FILE, "w").close()

# ── load only the two wall patches ─────────────────────────────────────────
print("Loading wall patches …")
reader = OpenFOAMReader(FileName=FOAM_FILE)
reader.MeshRegions = ["patch/buildings"]
reader.CellArrays  = []
reader.PointArrays = []
reader.UpdatePipeline()
t500 = max(reader.TimestepValues)
reader.UpdatePipeline(time=t500)

# ── add height field ────────────────────────────────────────────────────────
calc_bld = Calculator(Input=reader)
calc_bld.AttributeType   = "Point Data"
calc_bld.ResultArrayName = "Height"
calc_bld.Function        = "coordsZ"
calc_bld.UpdatePipeline(time=t500)

# ── view ───────────────────────────────────────────────────────────────────
layout = CreateLayout(name="WallLayout")
view   = CreateRenderView()
AssignViewToLayout(view=view, layout=layout, hint=0)
view.ViewSize        = [1920, 1200]
view.Background      = [0.04, 0.04, 0.10]
view.OrientationAxesVisibility = 1

# ── colour map: height (plasma) ─────────────────────────────────────────────
lut = GetColorTransferFunction("Height")
lut.RescaleTransferFunction(0.0, 80.0)
lut.RGBPoints = [
     0.0,  0.27, 0.00, 0.33,
    16.0,  0.25, 0.28, 0.53,
    32.0,  0.13, 0.57, 0.55,
    55.0,  0.37, 0.79, 0.38,
    80.0,  0.99, 0.91, 0.14,
]
lut.ColorSpace = "RGB"
lut.NanColor   = [0.3, 0.3, 0.3]

# ── representation ─────────────────────────────────────────────────────────
rep = Show(calc_bld, view)
rep.Representation      = "Surface With Edges"
ColorBy(rep, ("POINTS", "Height"))
rep.LookupTable         = lut
rep.EdgeColor           = [0.06, 0.06, 0.14]
rep.LineWidth           = 0.5
rep.Opacity             = 1.0
rep.SetScalarBarVisibility(view, True)

sb = GetScalarBar(lut, view)
sb.Title          = "Height  (m)"
sb.ComponentTitle = ""
sb.Visibility     = 1
sb.TitleFontSize  = 16
sb.LabelFontSize  = 13
sb.WindowLocation = "Lower Right Corner"

# ── camera: isometric SW looking NE ────────────────────────────────────────
view.CameraParallelProjection = 0
view.CameraPosition   = [-1600, -2000, 1400]
view.CameraFocalPoint = [  150,     0,   30]
view.CameraViewUp     = [    0,     0,    1]

RenderAllViews()
ResetCamera(view)
RenderAllViews()

out = os.path.join(SCRIPT_DIR, "pv_walls_buildings_only.png")
SaveScreenshot(out, view, ImageResolution=[1920, 1200])
print(f"  saved → pv_walls_buildings_only.png")
print("All done.")
