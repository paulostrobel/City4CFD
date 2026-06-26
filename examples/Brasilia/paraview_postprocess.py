"""
Brasília Congress — ParaView post-processing script
====================================================
Generates PNG screenshots of CFD results using paraview.simple.

Run headlessly:
    DISPLAY=:0 LIBGL_ALWAYS_SOFTWARE=1 pvbatch paraview_postprocess.py

Or inside the ParaView GUI:
    Tools → Python Shell → execfile("paraview_postprocess.py")

Output PNGs land next to this script.
"""
import os
from paraview.simple import (
    OpenFOAMReader,
    Slice,
    StreamTracerWithCustomSource,
    Line as PVLine,
    GetColorTransferFunction,
    GetOpacityTransferFunction,
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

# ── paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CASE_DIR   = os.path.join(SCRIPT_DIR, "openfoam")
FOAM_FILE  = os.path.join(CASE_DIR, "Brasilia.foam")

if not os.path.exists(FOAM_FILE):
    open(FOAM_FILE, "w").close()

# ── colour-map definitions (RGBPoints: val R G B repeating) ────────────────
# jet: blue→cyan→green→yellow→red
def _jet(vmin, vmax):
    v0, v1 = vmin, vmax
    d = v1 - v0
    return [
        v0,           0.0, 0.0, 0.5,
        v0 + d*0.125, 0.0, 0.0, 1.0,
        v0 + d*0.375, 0.0, 1.0, 1.0,
        v0 + d*0.5,   0.0, 1.0, 0.0,
        v0 + d*0.625, 1.0, 1.0, 0.0,
        v0 + d*0.875, 1.0, 0.0, 0.0,
        v1,           0.5, 0.0, 0.0,
    ]

# cool-to-warm: blue→white→red
def _c2w(vmin, vmax):
    v0, v1 = vmin, vmax
    mid = (v0 + v1) / 2.0
    return [
        v0,  0.23, 0.30, 0.75,
        mid, 0.87, 0.87, 0.87,
        v1,  0.71, 0.02, 0.15,
    ]

# black-body: black→red→orange→yellow→white
def _bb(vmin, vmax):
    v0, v1 = vmin, vmax
    d = v1 - v0
    return [
        v0,           0.0, 0.0, 0.0,
        v0 + d*0.40,  0.9, 0.0, 0.0,
        v0 + d*0.70,  0.9, 0.6, 0.0,
        v0 + d*0.85,  1.0, 1.0, 0.0,
        v1,           1.0, 1.0, 1.0,
    ]

# viridis-like: purple→blue→green→yellow
def _viridis(vmin, vmax):
    v0, v1 = vmin, vmax
    d = v1 - v0
    return [
        v0,           0.27, 0.00, 0.33,
        v0 + d*0.25,  0.25, 0.28, 0.53,
        v0 + d*0.50,  0.13, 0.57, 0.55,
        v0 + d*0.75,  0.37, 0.79, 0.38,
        v1,           0.99, 0.91, 0.14,
    ]

def make_lut(field, vmin, vmax, cmap_fn):
    lut = GetColorTransferFunction(field)
    lut.RescaleTransferFunction(vmin, vmax)
    lut.RGBPoints    = cmap_fn(vmin, vmax)
    lut.ColorSpace   = "RGB"
    lut.NanColor     = [0.5, 0.5, 0.5]
    return lut

lut_U   = make_lut("U",   0.0,  9.0,  _jet)
lut_p   = make_lut("p",  -5.0,  5.0,  _c2w)
lut_k   = make_lut("k",   0.0,  3.0,  _bb)
lut_nut = make_lut("nut", 0.0,  0.05, _viridis)

# ── view / layout factory ───────────────────────────────────────────────────
_n = [0]

def new_view(w=1600, h=900):
    layout = CreateLayout(name=f"L{_n[0]}")
    _n[0] += 1
    view = CreateRenderView()
    AssignViewToLayout(view=view, layout=layout, hint=0)
    view.ViewSize   = [w, h]
    view.Background = [0.05, 0.05, 0.12]
    view.OrientationAxesVisibility = 1
    return view

def snap(view, fname, w=1600, h=900):
    RenderAllViews()
    ResetCamera(view)
    RenderAllViews()
    path = os.path.join(SCRIPT_DIR, fname)
    SaveScreenshot(path, view, ImageResolution=[w, h])
    print(f"  saved → {fname}")

def show_scalar(src, view, field, lut, vector=False):
    rep = Show(src, view)
    if vector:
        ColorBy(rep, ("POINTS", field, "Magnitude"))
    else:
        ColorBy(rep, ("POINTS", field))
    rep.LookupTable = lut
    rep.SetScalarBarVisibility(view, True)
    sb = GetScalarBar(lut, view)
    sb.Visibility    = 1
    sb.TitleFontSize = 14
    sb.LabelFontSize = 11
    return rep

def top_down_view(w=1600, h=900):
    view = new_view(w, h)
    view.CameraParallelProjection = 1
    view.CameraPosition   = [500,  0, 6000]
    view.CameraFocalPoint = [500,  0,    0]
    view.CameraViewUp     = [  0,  1,    0]
    return view

# ── load case ──────────────────────────────────────────────────────────────
print("Loading OpenFOAM case …")
reader = OpenFOAMReader(FileName=FOAM_FILE)
reader.MeshRegions = ["internalMesh"]
reader.CellArrays  = ["U", "p", "k", "epsilon", "nut"]
reader.UpdatePipeline()
t500 = max(reader.TimestepValues)
reader.UpdatePipeline(time=t500)
print(f"  t = {t500}")

# ══════════════════════════════════════════════════════════════════════════
# 1. |U| at z = 1.75 m
# ══════════════════════════════════════════════════════════════════════════
print("\n[1] |U| z=1.75 m")
sl = Slice(Input=reader)
sl.SliceType = "Plane"
sl.SliceType.Origin = [0, 0, 1.75]
sl.SliceType.Normal = [0, 0, 1]
sl.UpdatePipeline(time=t500)

view = top_down_view()
show_scalar(sl, view, "U", lut_U, vector=True)
snap(view, "pv_U_z0175cm.png")

# ══════════════════════════════════════════════════════════════════════════
# 2. |U| at z = 10 m
# ══════════════════════════════════════════════════════════════════════════
print("\n[2] |U| z=10 m")
sl10 = Slice(Input=reader)
sl10.SliceType = "Plane"
sl10.SliceType.Origin = [0, 0, 10.0]
sl10.SliceType.Normal = [0, 0, 1]
sl10.UpdatePipeline(time=t500)

view = top_down_view()
show_scalar(sl10, view, "U", lut_U, vector=True)
snap(view, "pv_U_z1000cm.png")

# ══════════════════════════════════════════════════════════════════════════
# 3. |U| at z = 50 m
# ══════════════════════════════════════════════════════════════════════════
print("\n[3] |U| z=50 m")
sl50 = Slice(Input=reader)
sl50.SliceType = "Plane"
sl50.SliceType.Origin = [0, 0, 50.0]
sl50.SliceType.Normal = [0, 0, 1]
sl50.UpdatePipeline(time=t500)

view = top_down_view()
show_scalar(sl50, view, "U", lut_U, vector=True)
snap(view, "pv_U_z5000cm.png")

# ══════════════════════════════════════════════════════════════════════════
# 4. Pressure p at z = 1.75 m
# ══════════════════════════════════════════════════════════════════════════
print("\n[4] pressure z=1.75 m")
sl_p = Slice(Input=reader)
sl_p.SliceType = "Plane"
sl_p.SliceType.Origin = [0, 0, 1.75]
sl_p.SliceType.Normal = [0, 0, 1]
sl_p.UpdatePipeline(time=t500)

view = top_down_view()
show_scalar(sl_p, view, "p", lut_p)
snap(view, "pv_p_z175cm.png")

# ══════════════════════════════════════════════════════════════════════════
# 5. TKE k at z = 1.75 m
# ══════════════════════════════════════════════════════════════════════════
print("\n[5] TKE k z=1.75 m")
sl_k = Slice(Input=reader)
sl_k.SliceType = "Plane"
sl_k.SliceType.Origin = [0, 0, 1.75]
sl_k.SliceType.Normal = [0, 0, 1]
sl_k.UpdatePipeline(time=t500)

view = top_down_view()
show_scalar(sl_k, view, "k", lut_k)
snap(view, "pv_k_z175cm.png")

# ══════════════════════════════════════════════════════════════════════════
# 6. Turbulent viscosity nut at z = 1.75 m
# ══════════════════════════════════════════════════════════════════════════
print("\n[6] nut z=1.75 m")
sl_nut = Slice(Input=reader)
sl_nut.SliceType = "Plane"
sl_nut.SliceType.Origin = [0, 0, 1.75]
sl_nut.SliceType.Normal = [0, 0, 1]
sl_nut.UpdatePipeline(time=t500)

view = top_down_view()
show_scalar(sl_nut, view, "nut", lut_nut)
snap(view, "pv_nut_z175cm.png")

# ══════════════════════════════════════════════════════════════════════════
# 7. XZ vertical slice |U| (y=0)
# ══════════════════════════════════════════════════════════════════════════
print("\n[7] XZ slice y=0")
sl_xz = Slice(Input=reader)
sl_xz.SliceType = "Plane"
sl_xz.SliceType.Origin = [0, 0, 0]
sl_xz.SliceType.Normal = [0, 1, 0]
sl_xz.UpdatePipeline(time=t500)

view = new_view(1800, 700)
view.CameraParallelProjection = 1
view.CameraPosition   = [500, -8000,  150]
view.CameraFocalPoint = [500,     0,  150]
view.CameraViewUp     = [  0,     0,    1]
show_scalar(sl_xz, view, "U", lut_U, vector=True)
snap(view, "pv_U_XZ_y0.png", w=1800, h=700)

# ══════════════════════════════════════════════════════════════════════════
# 8. YZ vertical slice |U| (x=0)
# ══════════════════════════════════════════════════════════════════════════
print("\n[8] YZ slice x=0")
sl_yz = Slice(Input=reader)
sl_yz.SliceType = "Plane"
sl_yz.SliceType.Origin = [0, 0, 0]
sl_yz.SliceType.Normal = [1, 0, 0]
sl_yz.UpdatePipeline(time=t500)

view = new_view(1200, 900)
view.CameraParallelProjection = 1
view.CameraPosition   = [8000, 0, 150]
view.CameraFocalPoint = [   0, 0, 150]
view.CameraViewUp     = [   0, 0,   1]
show_scalar(sl_yz, view, "U", lut_U, vector=True)
snap(view, "pv_U_YZ_x0.png", w=1200, h=900)

# ══════════════════════════════════════════════════════════════════════════
# 9. Streamlines — 3-D isometric
# ══════════════════════════════════════════════════════════════════════════
print("\n[9] Streamlines 3D")
seed = PVLine()
seed.Point1     = [-1700, -800,   1.75]
seed.Point2     = [-1700,  800, 100.0]
seed.Resolution = 60

streams = StreamTracerWithCustomSource(Input=reader, SeedSource=seed)
streams.Vectors                 = ["POINTS", "U"]
streams.MaximumStreamlineLength = 12000.0
streams.IntegrationDirection    = "FORWARD"
streams.UpdatePipeline(time=t500)

view = new_view(1600, 900)
view.CameraPosition   = [-2800, -2400, 1800]
view.CameraFocalPoint = [  400,     0,  100]
view.CameraViewUp     = [    0,     0,    1]
rep = Show(streams, view)
ColorBy(rep, ("POINTS", "U", "Magnitude"))
rep.LookupTable = lut_U
rep.LineWidth   = 1.5
rep.SetScalarBarVisibility(view, True)
snap(view, "pv_streamlines_3d.png")

# ══════════════════════════════════════════════════════════════════════════
# 10. Streamlines — XZ side view
# ══════════════════════════════════════════════════════════════════════════
print("\n[10] Streamlines XZ side")
view2 = new_view(1800, 700)
view2.CameraParallelProjection = 1
view2.CameraPosition   = [500, -8000, 100]
view2.CameraFocalPoint = [500,     0, 100]
view2.CameraViewUp     = [  0,     0,   1]
rep2 = Show(streams, view2)
ColorBy(rep2, ("POINTS", "U", "Magnitude"))
rep2.LookupTable = lut_U
rep2.LineWidth   = 1.5
rep2.SetScalarBarVisibility(view2, True)
snap(view2, "pv_streamlines_XZ.png", w=1800, h=700)

# ══════════════════════════════════════════════════════════════════════════
# 11. Pedestrian zoom ±500 m
# ══════════════════════════════════════════════════════════════════════════
print("\n[11] Pedestrian zoom")
sl_zoom = Slice(Input=reader)
sl_zoom.SliceType = "Plane"
sl_zoom.SliceType.Origin = [0, 0, 1.75]
sl_zoom.SliceType.Normal = [0, 0, 1]
sl_zoom.UpdatePipeline(time=t500)

view = new_view(1200, 1000)
view.CameraParallelProjection = 1
view.CameraPosition    = [0, 0, 3000]
view.CameraFocalPoint  = [0, 0, 1.75]
view.CameraViewUp      = [0, 1,    0]
view.CameraParallelScale = 520
show_scalar(sl_zoom, view, "U", lut_U, vector=True)
snap(view, "pv_U_pedestrian_zoom.png", w=1200, h=1000)

print("\nAll done.")
