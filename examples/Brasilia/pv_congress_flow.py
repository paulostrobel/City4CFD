"""
ParaView script — detailed flow visualisation around the Congress complex.
Produces:
  pv_congress_U_pedestrian.png   — |U| at z=1.75m, zoomed on Congress
  pv_congress_streamlines.png    — 3-D streamlines coloured by |U|, Congress zoom
  pv_congress_U_XZ.png           — XZ vertical slice at y=0 (centreline)
  pv_congress_U_YZ.png           — YZ vertical slice at x=60 (through towers)

Run:
    DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 pvbatch pv_congress_flow.py
"""
import os
from paraview.simple import (
    OpenFOAMReader, Slice, StreamTracer, Tube,
    Calculator, GetColorTransferFunction,
    GetScalarBar, ColorBy, Show, Hide,
    CreateRenderView, CreateLayout, AssignViewToLayout,
    RenderAllViews, ResetCamera, SaveScreenshot,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_DIR   = os.path.join(SCRIPT_DIR, "openfoam")
FOAM_FILE  = os.path.join(CASE_DIR, "Brasilia.foam")

if not os.path.exists(FOAM_FILE):
    open(FOAM_FILE, "w").close()

# ── load case ─────────────────────────────────────────────────────────────────
print("Loading case …")
reader = OpenFOAMReader(FileName=FOAM_FILE)
reader.MeshRegions = ["internalMesh"]
reader.CellArrays  = ["U", "p", "k"]
reader.UpdatePipeline()
t500 = max(reader.TimestepValues)
reader.UpdatePipeline(time=t500)

# |U| calculator
calc = Calculator(Input=reader)
calc.AttributeType   = "Cell Data"
calc.ResultArrayName = "Umag"
calc.Function        = "mag(U)"
calc.UpdatePipeline(time=t500)

# ── colour map ────────────────────────────────────────────────────────────────
def jet_lut(vmin, vmax):
    lut = GetColorTransferFunction("Umag")
    lut.RescaleTransferFunction(vmin, vmax)
    d = vmax - vmin
    lut.RGBPoints = [
        vmin,          0.0, 0.0, 0.5,
        vmin+d*0.125,  0.0, 0.0, 1.0,
        vmin+d*0.375,  0.0, 1.0, 1.0,
        vmin+d*0.5,    0.0, 1.0, 0.0,
        vmin+d*0.625,  1.0, 1.0, 0.0,
        vmin+d*0.875,  1.0, 0.0, 0.0,
        vmax,          0.5, 0.0, 0.0,
    ]
    lut.ColorSpace = "RGB"
    return lut

def new_view(w=1920, h=1200, bg=[0.04,0.04,0.10]):
    layout = CreateLayout()
    view   = CreateRenderView()
    AssignViewToLayout(view=view, layout=layout, hint=0)
    view.ViewSize   = [w, h]
    view.Background = bg
    view.OrientationAxesVisibility = 1
    return view

def snap(view, fname, w=1920, h=1200):
    RenderAllViews()
    ResetCamera(view)
    RenderAllViews()
    path = os.path.join(SCRIPT_DIR, fname)
    SaveScreenshot(path, view, ImageResolution=[w, h])
    print(f"  saved → {fname}")

# ══════════════════════════════════════════════════════════════════════════════
# 1. Pedestrian-level |U| at z=1.75 m — Congress zoom  (already saved, skip)
# ══════════════════════════════════════════════════════════════════════════════
print("Pedestrian slice … (skipping, already saved)")
sl_z = Slice(Input=calc)
sl_z.SliceType              = "Plane"
sl_z.SliceType.Normal       = [0, 0, 1]
sl_z.SliceType.Origin       = [0, 0, 1.75]
sl_z.UpdatePipeline(time=t500)

lut = jet_lut(0, 7)
Hide(sl_z)

# ══════════════════════════════════════════════════════════════════════════════
# 2. 3-D streamlines — Congress zoom
# ══════════════════════════════════════════════════════════════════════════════
print("3-D streamlines …")
streams = StreamTracer(Input=reader)
streams.SeedType = "Point Cloud"
streams.SeedType.Center = [-600, -185, 60]
streams.SeedType.Radius = 200
streams.SeedType.NumberOfPoints = 60
streams.Vectors              = ["CELLS", "U"]
streams.MaximumSteps         = 5000
streams.IntegrationDirection = "FORWARD"
streams.UpdatePipeline(time=t500)

tubes = Tube(Input=streams)
tubes.Radius = 2.5
tubes.UpdatePipeline(time=t500)

lut2 = GetColorTransferFunction("Umag")
lut2.RescaleTransferFunction(0, 8)
lut2.RGBPoints = [
    0,   0.0, 0.0, 0.5,
    1,   0.0, 0.0, 1.0,
    3,   0.0, 1.0, 1.0,
    4,   0.0, 1.0, 0.0,
    5,   1.0, 1.0, 0.0,
    7,   1.0, 0.0, 0.0,
    8,   0.5, 0.0, 0.0,
]
lut2.ColorSpace = "RGB"

view2 = new_view()
rep2 = Show(tubes, view2)
rep2.Representation = "Surface"
ColorBy(rep2, ("POINTS", "Umag"))
rep2.LookupTable = lut2

view2.CameraParallelProjection = 0
view2.CameraPosition   = [-500, -600, 300]
view2.CameraFocalPoint = [ 100, -185,  30]
view2.CameraViewUp     = [   0,    0,   1]
snap(view2, "pv_congress_streamlines.png")

# ══════════════════════════════════════════════════════════════════════════════
# 3. XZ vertical slice at y=0 (centreline through towers)
# ══════════════════════════════════════════════════════════════════════════════
print("XZ slice (y=0) …")
sl_xz = Slice(Input=calc)
sl_xz.SliceType        = "Plane"
sl_xz.SliceType.Normal = [0, 1, 0]
sl_xz.SliceType.Origin = [0, 0, 0]
sl_xz.UpdatePipeline(time=t500)

view3 = new_view(w=1920, h=800)
lut3 = GetColorTransferFunction("Umag")
lut3.RescaleTransferFunction(0, 8)
lut3.RGBPoints = lut2.RGBPoints
lut3.ColorSpace = "RGB"
rep3 = Show(sl_xz, view3)
rep3.Representation = "Surface"
ColorBy(rep3, ("CELLS", "Umag"))
rep3.LookupTable = lut3

view3.CameraParallelProjection = 1
view3.CameraPosition   = [  60, -2000, 60]
view3.CameraFocalPoint = [  60,     0, 60]
view3.CameraViewUp     = [   0,     0,  1]
view3.CameraParallelScale = 120
snap(view3, "pv_congress_U_XZ.png", w=1920, h=800)

# ══════════════════════════════════════════════════════════════════════════════
# 4. YZ vertical slice at x=60 (through dome/bowl, N-S)
# ══════════════════════════════════════════════════════════════════════════════
print("YZ slice (x=60) …")
sl_yz = Slice(Input=calc)
sl_yz.SliceType        = "Plane"
sl_yz.SliceType.Normal = [1, 0, 0]
sl_yz.SliceType.Origin = [60, 0, 0]
sl_yz.UpdatePipeline(time=t500)

view4 = new_view(w=1920, h=800)
lut4 = GetColorTransferFunction("Umag")
lut4.RescaleTransferFunction(0, 8)
lut4.RGBPoints = lut2.RGBPoints
lut4.ColorSpace = "RGB"
rep4 = Show(sl_yz, view4)
rep4.Representation = "Surface"
ColorBy(rep4, ("CELLS", "Umag"))
rep4.LookupTable = lut4

view4.CameraParallelProjection = 1
view4.CameraPosition   = [2000, -185, 60]
view4.CameraFocalPoint = [   0, -185, 60]
view4.CameraViewUp     = [   0,    0,  1]
view4.CameraParallelScale = 220
snap(view4, "pv_congress_U_YZ.png", w=1920, h=800)

print("\nAll done.")
