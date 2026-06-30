"""
ParaView — front view of Congress complex matching the architectural photo.
Shows dome and bowl prominently with towers, from ground-level perspective.

Run:
    DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 pvbatch pv_congress_frontview.py
"""
import os
from paraview.simple import (
    OpenFOAMReader, Slice, StreamTracer, Tube,
    Calculator, Contour,
    GetColorTransferFunction, GetScalarBar, ColorBy, Show,
    CreateRenderView, CreateLayout, AssignViewToLayout,
    RenderAllViews, ResetCamera, SaveScreenshot,
)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_DIR   = os.path.join(SCRIPT_DIR, "openfoam")
FOAM_FILE  = os.path.join(CASE_DIR, "Brasilia.foam")

if not os.path.exists(FOAM_FILE):
    open(FOAM_FILE, "w").close()

print("Loading case …")
reader = OpenFOAMReader(FileName=FOAM_FILE)
reader.MeshRegions = ["internalMesh"]
reader.CellArrays  = ["U"]
reader.UpdatePipeline()
t500 = max(reader.TimestepValues)
reader.UpdatePipeline(time=t500)

calc = Calculator(Input=reader)
calc.AttributeType   = "Cell Data"
calc.ResultArrayName = "Umag"
calc.Function        = "mag(U)"
calc.UpdatePipeline(time=t500)

# ── Vertical slice through Congress (XZ at y=−185, N-S centreline) ───────────
print("Creating vertical slice …")
sl = Slice(Input=calc)
sl.SliceType        = "Plane"
sl.SliceType.Normal = [0, 1, 0]
sl.SliceType.Origin = [0, -185, 0]
sl.UpdatePipeline(time=t500)

# ── Velocity isosurfaces ───────────────────────────────────────────────────
print("Creating isosurfaces …")
iso = Contour(Input=sl)
iso.ContourBy       = ["CELLS", "Umag"]
iso.Isosurfaces     = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
iso.UpdatePipeline(time=t500)

# ── Streamlines approaching from west ──────────────────────────────────────
print("Creating streamlines …")
streams = StreamTracer(Input=reader)
streams.SeedType = "Point Cloud"
streams.SeedType.Center      = [-800, -185, 40]
streams.SeedType.Radius      = 200
streams.SeedType.NumberOfPoints = 100
streams.Vectors              = ["CELLS", "U"]
streams.MaximumSteps         = 10000
streams.IntegrationDirection = "FORWARD"
streams.UpdatePipeline(time=t500)

tubes = Tube(Input=streams)
tubes.Radius = 2.5
tubes.UpdatePipeline(time=t500)

# ── Setup view ────────────────────────────────────────────────────────────────
layout = CreateLayout()
view   = CreateRenderView()
AssignViewToLayout(view=view, layout=layout, hint=0)
view.ViewSize   = [1920, 1440]
view.Background = [0.4, 0.6, 0.95]  # sky blue
view.OrientationAxesVisibility = 0

# ── Velocity colormap ─────────────────────────────────────────────────────────
lut = GetColorTransferFunction("Umag")
lut.RescaleTransferFunction(0, 8)
lut.RGBPoints = [
    0,   0.0, 0.3, 0.8,
    1,   0.0, 0.5, 1.0,
    2,   0.0, 1.0, 1.0,
    3,   0.2, 1.0, 0.2,
    4,   1.0, 1.0, 0.0,
    6,   1.0, 0.5, 0.0,
    8,   1.0, 0.0, 0.0,
]
lut.ColorSpace = "RGB"

# ── Show isosurfaces ──────────────────────────────────────────────────────────
rep_iso = Show(iso, view)
rep_iso.Representation = "Surface With Edges"
ColorBy(rep_iso, ("CELLS", "Umag"))
rep_iso.LookupTable     = lut
rep_iso.LineWidth       = 1.0
rep_iso.EdgeColor       = [0.1, 0.1, 0.2]
rep_iso.Opacity         = 0.75

# ── Show streamlines ──────────────────────────────────────────────────────────
lut2 = GetColorTransferFunction("Umag")
lut2.RescaleTransferFunction(0, 8)
lut2.RGBPoints = lut.RGBPoints
lut2.ColorSpace = "RGB"

rep_tubes = Show(tubes, view)
rep_tubes.Representation = "Surface"
ColorBy(rep_tubes, ("POINTS", "Umag"))
rep_tubes.LookupTable    = lut2
rep_tubes.Opacity        = 0.85

# ── Scalar bar ────────────────────────────────────────────────────────────────
sb = GetScalarBar(lut, view)
sb.Title            = "Wind Speed (m/s)"
sb.ComponentTitle   = ""
sb.Visibility       = 1
sb.TitleFontSize    = 16
sb.LabelFontSize    = 12
sb.WindowLocation   = "Lower Right Corner"

# ── Camera: from WEST (−X) looking EAST (+X) at Congress ───────────────────
# Low angle to show dome and bowl prominently, like the architectural photo
# Position at ground level (z ≈ 0-10), looking at structures
view.CameraParallelProjection = 0
view.CameraPosition   = [-900, -185, 15]    # far left, low angle
view.CameraFocalPoint = [ 100, -185, 40]    # looking at towers/dome/bowl
view.CameraViewUp     = [   0,    0,   1]

RenderAllViews()
ResetCamera(view)
RenderAllViews()

out = os.path.join(SCRIPT_DIR, "pv_congress_frontview.png")
SaveScreenshot(out, view, ImageResolution=[1920, 1440])
print(f"saved → pv_congress_frontview.png")
print("Done.")
