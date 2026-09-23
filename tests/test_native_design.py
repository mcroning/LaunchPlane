"""Native acceptance: signed intent and unscaled host rays, not target editing."""
import math
from dataclasses import replace
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPointF
from PySide6.QtWidgets import QApplication
from launchplane.model import BeamDefinition, BeamStackDefinition
from launchplane.serialization import beam_stack_to_dict, beam_stack_from_dict
from launchplane.launchpane import LaunchPlaneWidget


@pytest.mark.parametrize('phi', [0,.7,math.pi/2,math.pi,3*math.pi/2])
def test_signed_intent_equivalence_and_persistence(phi):
    negative = BeamDefinition(theta_ext_rad=-.4, phi_rad=phi, psi_rad=.37)
    positive = replace(negative, theta_ext_rad=.4, phi_rad=phi+math.pi)
    assert negative.external_wavevector_rad_per_um == pytest.approx(positive.external_wavevector_rad_per_um)
    stack = BeamStackDefinition(beams=(negative,))
    assert beam_stack_from_dict(beam_stack_to_dict(stack)) == stack
    assert stack.beams[0].theta_ext_rad == -.4


def test_coincident_labels_fit_and_full_aperture_restore():
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=BeamStackDefinition(beams=tuple(
        BeamDefinition(name=f'long beam name {i}',theta_ext_rad=(-1)**i*.4) for i in range(4))))
    try:
        widget.resize(1100,850); widget.show(); app.processEvents()
        before = widget.beam_stack
        contour = [(20.,0.),(0.,20.),(-20.,0.),(0.,-20.)]
        endpoints = [(1000.,500.),(-1000.,-500.),(1500.,0.),(0.,0.)]
        widget.set_resolved_preview([contour]*4, description='host', ray_endpoints=endpoints)
        widget.fit_button.click(); app.processEvents()
        visible = widget.view.mapToScene(widget.view.viewport().rect()).boundingRect()
        for endpoint in endpoints:
            assert visible.contains(QPointF(endpoint[0],-endpoint[1]))
        for width in (950,1200,1450):
            widget.resize(width,850); app.processEvents()
            widget.view.arrange_beam_labels()
            rects = [i._label.deviceTransform(widget.view.viewportTransform()).mapRect(i._label.boundingRect())
                     for i in widget.scene.beam_items]
            assert all(not a.intersects(b) for j,a in enumerate(rects) for b in rects[j+1:])
            assert [i._label.text() for i in widget.scene.beam_items] == ['1','2','3','4']
        widget.full_aperture_button.click(); app.processEvents()
        visible = widget.view.mapToScene(widget.view.viewport().rect()).boundingRect()
        assert visible.contains(widget.scene.sceneRect())
        assert not visible.contains(QPointF(1500,0))
        assert widget.beam_stack == before
        assert widget.scene.beam_items[2].tilt_tip_offset() == QPointF(1500,0)
        assert len(widget._resolved_items) == 4
        assert widget.canvas_title.text() == 'Input face'
        with pytest.raises(ValueError):
            widget.set_resolved_preview([], description='bad',ray_endpoints=[(float('nan'),0)]*4)
        assert len(widget._resolved_items) == 4
    finally:
        widget.close(); widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete); app.processEvents()


def test_arrowhead_stays_visible_at_long_ray_fit_without_moving_endpoint():
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=BeamStackDefinition(beams=(BeamDefinition(theta_ext_rad=.4),)))
    try:
        widget.set_resolved_preview([],description='host',ray_endpoints=[(10000.,2000.)])
        item=widget.scene.beam_items[0]
        for scale in (.001,.1,1,10):
            widget.view._set_scale(scale)
            head=item._ray_head
            assert head.isVisible()
            assert head.scenePos()==QPointF(10000,-2000)
            device=head.deviceTransform(widget.view.viewportTransform())
            tip=device.map(QPointF())
            corner=device.map(QPointF(-8,4))
            assert math.hypot((tip-corner).x(),(tip-corner).y())==pytest.approx(math.sqrt(80))
    finally:
        widget.close();widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()


def test_crossing_rays_keep_distinct_entrances_and_physical_exits():
    app = QApplication.instance() or QApplication([])
    widget = LaunchPlaneWidget(beam_stack=BeamStackDefinition(beams=(
        BeamDefinition(name='left',x_um=-20,theta_ext_rad=.4),
        BeamDefinition(name='right',x_um=20,theta_ext_rad=-.4))))
    try:
        widget.set_resolved_preview([],description='host crossing',ray_endpoints=[(20,0),(-20,0)])
        left,right=widget.scene.beam_items
        assert left.pos()==QPointF(-20,0) and right.pos()==QPointF(20,0)
        assert left._ray_head.scenePos()==QPointF(20,0)
        assert right._ray_head.scenePos()==QPointF(-20,0)
        for item in (left,right):
            assert item.pos()+item.tilt_tip_offset()/2==QPointF()
        widget.fit_button.click()
        assert left.tilt_tip_offset()==QPointF(40,0)
        assert right.tilt_tip_offset()==QPointF(-40,0)
    finally:
        widget.close();widget.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
