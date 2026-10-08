"""Canvas labels inherit the host application's resolved font."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPointF, qInstallMessageHandler
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QGraphicsItem
from launchplane.launchpane import LaunchPlaneWidget, example_beam_stack


def test_canvas_inherits_resolved_font_without_alias_warning():
    app = QApplication.instance() or QApplication([])
    original = app.font()
    # A concrete installed family models the host application's resolved font.
    families = QFontDatabase.families()
    family = next((n for n in (original.family(), "Arial", "DejaVu Sans", "Liberation Sans") if n in families), families[0])
    font = QFont(original); font.setFamily(family); app.setFont(font)
    messages = []
    old_handler = qInstallMessageHandler(lambda kind, context, text: messages.append(text))
    widget = None
    try:
        widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
        for beam in widget.scene.beam_items:
            label = beam._label
            assert label.font().family() == family
            assert label.font().pointSize() == 12 and label.font().bold()
            assert label.pos() == QPointF(8., -18.)
            assert label.flags() & QGraphicsItem.ItemIgnoresTransformations
        for bold in (False, True):
            label = widget.scene._add_axis_text("x", QPointF(2.,3.), point_size=9, bold=bold, rotation=90.)
            assert label.font().family() == family
            assert label.font().pointSize() == 9 and label.font().bold() == bold
            assert label.pos() == QPointF(2.,3.) and label.rotation() == 90.
        widget.show(); app.processEvents()
        assert not any("font family" in text.lower() and "sans serif" in text.lower() for text in messages), messages
    finally:
        if widget is not None: widget.close()
        qInstallMessageHandler(old_handler)
        app.setFont(original)
