import pytest
from PySide6.QtWidgets import QApplication
from launchplane.launchpane import LaunchPlaneWidget, example_beam_stack
from launchplane.serialization import beam_stack_to_dict


def test_host_contour_parity_physical_scaling_and_intent_invalidation():
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    try:
        before = beam_stack_to_dict(widget.beam_stack)
        contour = [(2., 3.), (7., 3.), (2., 11.)]
        widget.set_resolved_preview([contour], description='Host: internal angle 12 degrees')
        item = widget._resolved_items[0]
        assert (item.path().elementAt(0).x, item.path().elementAt(0).y) == (2., -3.)
        assert (item.path().elementAt(2).x, item.path().elementAt(2).y) == (2., -11.)
        bounds = item.sceneBoundingRect()
        widget.view.scale(2, 2)
        assert item.sceneBoundingRect() == bounds
        assert beam_stack_to_dict(widget.beam_stack) == before
        assert '12 degrees' in widget.execution_status.text()
        widget.object_list.setCurrentRow(0)
        widget.theta_spin.setValue(25.)
        assert not widget._resolved_items
        widget.set_resolved_preview([contour], description='refreshed')
        widget.scene.set_definition(widget.scene.definition)
        assert not widget._resolved_items
        widget.set_beam_stack(widget.beam_stack, 0)
        assert not widget._resolved_items
        assert 'requires a compatible host resolver' in widget.execution_status.text()
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


def test_invalid_host_contour_cannot_replace_good_preview():
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget()
    try:
        widget.set_resolved_preview([[(0, 0), (1, 0), (0, 1)]], description='valid')
        with pytest.raises(ValueError):
            widget.set_resolved_preview([[(0, 0), (1, float('nan')), (0, 1)]], description='invalid')
        assert widget.execution_status.text().startswith('valid')
        assert len(widget._resolved_items) == 1
    finally:
        widget.close()
        widget.deleteLater()
        app.processEvents()


@pytest.mark.parametrize('width', [850, 1100, 1450])
def test_canvas_annotations_use_nonoverlapping_wrapping_layout(width):
    from PySide6.QtCore import QCoreApplication, QEvent
    from launchplane.model import LaunchPlaneDefinition
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=example_beam_stack())
    try:
        widget.resize(width, 850)
        widget.show()
        for target_width in (width, width + 73, width):
            widget.resize(target_width, 850)
            widget.view.fit_aperture()
            app.processEvents()
            title, bounds, view = widget.canvas_title, widget.canvas_bounds, widget.view
            assert title.isVisible() and bounds.isVisible() and view.isVisible()
            assert title.geometry().bottom() < bounds.geometry().top()
            assert bounds.geometry().bottom() < view.geometry().top()
            assert title.height() >= title.heightForWidth(title.width())
            assert bounds.height() >= bounds.heightForWidth(bounds.width())
            assert title.wordWrap() and bounds.wordWrap()
            old = (title.geometry(), bounds.geometry())
            widget.view.scale(1.7, 1.7)
            app.processEvents()
            assert old == (title.geometry(), bounds.geometry())
        widget.scene.set_definition(LaunchPlaneDefinition(x_aperture_um=240., y_aperture_um=120.))
        assert widget.canvas_bounds.text() == 'x: -120 … 120 µm    y: -60 … 60 µm'
    finally:
        widget.close()
        widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)
        app.processEvents()
