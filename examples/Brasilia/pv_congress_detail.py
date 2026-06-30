"""
ParaView — detailed pedestrian-level view of Congress complex.
Shows velocity magnitude contours and streamlines at z=1.75m,
with 3D structures (dome, bowl, towers) visible.

Run:
    DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 pvbatch pv_congress_detail.py
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

# |U| magnitude
calc = Calculator(Input=reader)
calc.AttributeType   = "Cell Data"
calc.ResultArrayName = "Umag"
calc.Function        = "mag(U)"
calc.UpdatePipeline(time=t500)

# ── Pedestrian slice at z=1.75 m ─────────────────────────────────────────────
print("Creating pedestrian slice …")
sl = Slice(Input=calc)
sl.SliceType        = "Plane"
sl.SliceType.Normal = [0, 0, 1]
sl.SliceType.Origin = [0, 0, 1.75]
sl.UpdatePipeline(time=t500)

# ── Velocity magnitude isosurfaces (contours) ────────────────────────────────
print("Creating velocity isosurfaces …")
iso = Contour(Input=sl)
iso.ContourBy       = ["CELLS", "Umag"]
iso.Isosurfaces     = [1.5, 2.5, 3.5, 4.5, 5.5, 6.0]
iso.UpdatePipeline(time=t500)

# ── Streamlines from seed points west of Congress ───────────────────────────
print("Creating streamlines …")
streams = StreamTracer(Input=reader)
streams.SeedType = "Point Cloud"
streams.SeedType.Center      = [-600, -185, 10]
streams.SeedType.Radius      = 250
streams.SeedType.NumberOfPoints = 80
streams.Vectors              = ["CELLS", "U"]
streams.MaximumSteps         = 8000
streams.IntegrationDirection = "FORWARD"
streams.UpdatePipeline(time=t500)

tubes = Tube(Input=streams)
tubes.Radius = 3.0
tubes.UpdatePipeline(time=t500)

# ── Setup view ────────────────────────────────────────────────────────────────
layout = CreateLayout()
view   = CreateRenderView()
AssignViewToLayout(view=view, layout=layout, hint=0)
view.ViewSize   = [2560, 1600]
view.Background = [0.03, 0.03, 0.08]
view.OrientationAxesVisibility = 1

# ── Velocity colormap (blue → red) ────────────────────────────────────────────
lut = GetColorTransferFunction("Umag")
lut.RescaleTransferFunction(0, 8)
lut.RGBPoints = [
    0,   0.0, 0.0, 0.7,
    1,   0.0, 0.0, 1.0,
    2,   0.0, 1.0, 1.0,
    3,   0.0, 1.0, 0.0,
    4,   1.0, 1.0, 0.0,
    6,   1.0, 0.5, 0.0,
    8,   1.0, 0.0, 0.0,
]
lut.ColorSpace = "RGB"

# ── Show velocity slice with contours ─────────────────────────────────────────
rep_iso = Show(iso, view)
rep_iso.Representation = "Surface With Edges"
ColorBy(rep_iso, ("CELLS", "Umag"))
rep_iso.LookupTable     = lut
rep_iso.LineWidth       = 1.5
rep_iso.EdgeColor       = [0.2, 0.2, 0.3]
rep_iso.AmbientColor    = [0.3, 0.3, 0.5]
rep_iso.Opacity         = 0.8

# ── Streamlines (tubes) ───────────────────────────────────────────────────────
lut2 = GetColorTransferFunction("Umag")
lut2.RescaleTransferFunction(0, 8)
lut2.RGBPoints = lut.RGBPoints
lut2.ColorSpace = "RGB"

rep_tubes = Show(tubes, view)
rep_tubes.Representation = "Surface"
ColorBy(rep_tubes, ("POINTS", "Umag"))
rep_tubes.LookupTable    = lut2
rep_tubes.Opacity        = 0.9

# ── Scalar bar ────────────────────────────────────────────────────────────────
sb = GetScalarBar(lut, view)
sb.Title            = "|U| (m/s)"
sb.ComponentTitle   = ""
sb.Visibility       = 1
sb.TitleFontSize    = 18
sb.LabelFontSize    = 14
sb.WindowLocation   = "Lower Right Corner"

# ── Camera: angled view from SW, looking NE at Congress complex ──────────────
# Position allows seeing dome (north), bowl (south), and towers (center)
view.CameraParallelProjection = 0
view.CameraPosition   = [-400, -600, 150]
view.CameraFocalPoint = [ 80, -180,  20]
view.CameraViewUp     = [  0,    0,   1]

RenderAllViews()
ResetCamera(view)
RenderAllViews()

out = os.path.join(SCRIPT_DIR, "pv_congress_pedestrian_detail.png")
SaveScreenshot(out, view, ImageResolution=[2560, 1600])
print(f"saved → pv_congress_pedestrian_detail.png")
print("Done.")
