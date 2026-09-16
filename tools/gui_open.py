"""
Opened by tools/open_gui.sh inside the FreeCAD GUI.

A document written by freecadcmd contains no GuiDocument.xml - headless
FreeCAD has no view providers, so nothing about visibility, colour or camera
is saved. Opening such a file leaves group members hidden and the camera
wherever it happened to be, which looks exactly like an empty document.

This script supplies the missing view state: it shows the parts, hides the
reference head, colours the components so they can be told apart, and fits
the camera to the model.

Target file comes from DIVIDER_GUI_TARGET.
"""

import os

import FreeCAD as App
import FreeCADGui as Gui

# Objects hidden on open: the reference head is a 150x190x250 mm ellipsoid
# that swallows the entire mechanism.
HIDE_ON_OPEN = ("HeadReference",)

# (r, g, b) in 0..1.
COLOURS = {
    "BallStud": (0.30, 0.45, 0.70),      # blue
    "Socket": (0.75, 0.75, 0.72),        # grey
    "Collar": (0.90, 0.55, 0.15),        # orange
}
REFERENCE_COLOUR = (0.85, 0.15, 0.15)    # red - datum points and radii


def _open(target):
    if not target or not os.path.isfile(target):
        App.Console.PrintError("gui_open: no such file: %r\n" % target)
        return None
    if target.lower().endswith(".fcstd"):
        return App.openDocument(target)
    import Import                          # STEP and friends
    doc = App.newDocument(os.path.splitext(os.path.basename(target))[0])
    Import.insert(target, doc.Name)
    return doc


def _style(doc):
    for obj in doc.Objects:
        vo = getattr(obj, "ViewObject", None)
        if vo is None:
            continue
        try:
            vo.Visibility = obj.Name not in HIDE_ON_OPEN
            base = obj.Name.rsplit("_", 1)[0]
            if base in COLOURS and hasattr(vo, "ShapeColor"):
                vo.ShapeColor = COLOURS[base]
            elif obj.Name.isupper() or obj.Name.startswith("Radius"):
                # datum points and the two radius lines
                if hasattr(vo, "PointColor"):
                    vo.PointColor = REFERENCE_COLOUR
                    vo.PointSize = 8.0
                if hasattr(vo, "LineColor"):
                    vo.LineColor = REFERENCE_COLOUR
                    vo.LineWidth = 2.0
            elif obj.Name == "HeadReference" and hasattr(vo, "Transparency"):
                # stays hidden, but is see-through if switched back on
                vo.Transparency = 80
        except Exception as exc:
            App.Console.PrintWarning("gui_open: %s: %s\n" % (obj.Name, exc))


def main():
    doc = _open(os.environ.get("DIVIDER_GUI_TARGET", ""))
    if doc is None:
        return
    doc.recompute()
    _style(doc)
    view = Gui.activeDocument().activeView()
    view.viewAxonometric()
    Gui.SendMsgToActiveView("ViewFit")
    App.Console.PrintMessage(
        "gui_open: %s ready - %d objects, HeadReference hidden, view fitted\n"
        % (doc.Name, len(doc.Objects)))


main()
