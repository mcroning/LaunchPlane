"""Real viewport events; a synthetic host tests dispatch, not optical physics."""
from dataclasses import replace
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from launchplane.launchpane import LaunchPlaneWidget
from launchplane.model import BeamDefinition, BeamStackDefinition, LaunchPlaneDefinition


@pytest.fixture
def editor():
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(launch_plane=LaunchPlaneDefinition(x_aperture_um=200,y_aperture_um=200), beam_stack=BeamStackDefinition(beams=(BeamDefinition(),)))
    calls = []
    # Synthetic, deliberately non-optical host seam. Product tests use the real inverse.
    def inverse(beam, x, y):
        calls.append((beam, x, y))
        return (x-beam.x_um)/10000, ((y-beam.y_um)/10000) % 6.283185307179586
    widget.set_inverse_resolver(inverse)
    def preview(stack):
        endpoints = [(b.x_um+10000*b.theta_ext_rad,
                      b.y_um+10000*(b.phi_rad if b.phi_rad < 3.14 else b.phi_rad-6.283185307179586))
                     for b in stack.beams]
        widget.set_resolved_preview([[(0,0),(30,0),(0,30)]],
                                   description='synthetic host', ray_endpoints=endpoints)
    widget.beamStackChanged.connect(preview)
    widget.resize(1100, 850); widget.show(); app.processEvents()
    preview(widget.beam_stack); widget.view.fit_aperture(); app.processEvents()
    try:
        yield app, widget, calls, preview
    finally:
        widget.close(); widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete); app.processEvents()


def drag(app, widget, handle, delta, *, grab_offset=QPoint()):
    view = widget.view
    app.processEvents()
    start = view.mapFromScene(handle.scenePos()) + grab_offset
    expected = view.mapToScene(start+delta)-view.mapToScene(start)
    QTest.mousePress(view.viewport(), Qt.LeftButton, pos=start)
    assert widget.scene.mouseGrabberItem() is handle
    assert widget.scene.focusItem() is handle
    # More than one move catches lost grab during host preview redelivery.
    for fraction in (.5, 1.):
        QTest.mouseMove(view.viewport(), start+QPoint(round(delta.x()*fraction), round(delta.y()*fraction)))
        app.processEvents()
        assert widget.scene.mouseGrabberItem() is handle
    QTest.mouseRelease(view.viewport(), Qt.LeftButton, pos=start+delta)
    app.processEvents()
    return expected


@pytest.mark.parametrize('scale', [.02, 1., 20.])
def test_zero_overlap_drag_and_device_hit_target(editor, scale):
    app, widget, calls, preview = editor
    view = widget.view; view._set_scale(scale); view.centerOn(0, 0)
    item = widget.scene.beam_items[0]
    assert item._ray_head.isVisible()
    assert item._ray_head.scenePos() == item._center_marker.scenePos()
    # Five pixels beyond the physical point still hits the cosmetic target at any zoom.
    delta = drag(app, widget, item._ray_head, QPoint(36, -25), grab_offset=QPoint(4,0))
    beam = widget.beam_stack.beams[0]
    assert (beam.x_um,beam.y_um) == (0,0)
    assert calls[-1][1:] == pytest.approx((delta.x(),-delta.y()))
    assert item._ray_head.scenePos().x() == pytest.approx(delta.x())
    assert item._ray_head.scenePos().y() == pytest.approx(delta.y())
    # Exposed center remains independently interactive. Stay inside aperture at low zoom.
    before = widget.beam_stack.beams[0]
    delta = drag(app, widget, item._center_marker, QPoint(1, -1), grab_offset=QPoint(-4,0))
    after = widget.beam_stack.beams[0]
    assert (after.theta_ext_rad, after.phi_rad) == (before.theta_ext_rad,before.phi_rad)
    assert (after.x_um,after.y_um) == pytest.approx((delta.x(),-delta.y()))


def test_long_ray_fit_and_cross_beam_arrow_priority(editor):
    app, widget, calls, preview = editor
    widget.set_beam_stack(BeamStackDefinition(beams=(BeamDefinition(theta_ext_rad=1.), BeamDefinition(name='second',x_um=0))))
    preview(widget.beam_stack); widget.view.fit_all(); app.processEvents()
    first, second = widget.scene.beam_items
    original = first._ray_head.scenePos()
    delta = drag(app, widget, first._ray_head, QPoint(-20,10))
    assert first._ray_head.scenePos().x() == pytest.approx(original.x()+delta.x())
    # Different beams: second arrow at first center must beat first center.
    widget.view.fit_aperture(); app.processEvents()
    assert first._center_marker.scenePos() == second._ray_head.scenePos()
    drag(app, widget, second._ray_head, QPoint(30,-20))
    assert widget.beam_stack.beams[0].x_um == 0
    assert widget.beam_stack.beams[1].theta_ext_rad != 0
    assert widget.object_list.currentRow() == 1


@pytest.mark.parametrize('scale', [.2, 2., 12.])
def test_keyboard_device_nudges_and_spinbox_focus(editor, scale):
    app, widget, calls, preview = editor
    widget.set_beam_stack(BeamStackDefinition(beams=(BeamDefinition(theta_ext_rad=.01),)))
    preview(widget.beam_stack)
    widget.view._set_scale(scale); widget.view.centerOn(0,0)
    item = widget.scene.beam_items[0]
    center = item._center_marker
    QTest.mouseClick(widget.view.viewport(),Qt.LeftButton,pos=widget.view.mapFromScene(center.scenePos()))
    assert widget.scene.focusItem() is center
    QTest.keyClick(widget.view.viewport(),Qt.Key_Right)
    assert widget.beam_stack.beams[0].x_um == pytest.approx(1/scale)
    QTest.keyClick(widget.view.viewport(),Qt.Key_Up,Qt.ShiftModifier)
    assert widget.beam_stack.beams[0].y_um == pytest.approx(10/scale)
    head = item._ray_head
    widget.view.centerOn(head.scenePos())
    QTest.mouseClick(widget.view.viewport(),Qt.LeftButton,pos=widget.view.mapFromScene(head.scenePos()))
    before = head.scenePos()
    QTest.keyClick(widget.view.viewport(),Qt.Key_Left,Qt.ShiftModifier)
    assert head.scenePos().x() == pytest.approx(before.x()-10/scale)
    QTest.keyClick(widget.view.viewport(),Qt.Key_Down)
    assert head.scenePos().y() == pytest.approx(before.y()+1/scale)
    call_count = len(calls)
    center_before = (widget.beam_stack.beams[0].x_um,widget.beam_stack.beams[0].y_um)
    widget.theta_spin.setFocus(); app.processEvents()
    QTest.keyClick(widget.theta_spin,Qt.Key_Up)
    app.processEvents()
    assert len(calls) == call_count
    assert (widget.beam_stack.beams[0].x_um,widget.beam_stack.beams[0].y_um) == center_before
    # Returning to the canvas restores keyboard handle editing.
    widget.view.centerOn(head.scenePos())
    QTest.mouseClick(widget.view.viewport(),Qt.LeftButton,pos=widget.view.mapFromScene(head.scenePos()))
    QTest.keyClick(widget.view.viewport(),Qt.Key_Right)
    assert len(calls) == call_count+1


def test_unavailable_inverse_and_failed_redelivery_are_explicit(editor):
    app, widget, calls, preview = editor
    widget.set_inverse_resolver(None)
    head = widget.scene.beam_items[0]._ray_head
    drag(app,widget,head,QPoint(20,0))
    assert widget.beam_stack.beams[0].theta_ext_rad == 0
    assert 'unavailable' in widget.execution_status.text()
    # Without a host redelivery a changed stack cannot keep stale physical rays.
    widget.beamStackChanged.disconnect(preview)
    widget.theta_spin.setValue(10)
    assert not head.isVisible()
