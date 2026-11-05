"""Responsive layout with unchanged host geometry and interactive handles."""
import pytest
from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtWidgets import QApplication
from launchplane.launchpane import LaunchPlaneWidget
from launchplane.model import BeamDefinition,BeamStackDefinition


@pytest.mark.parametrize('width,height',[(800,600),(1000,720),(1200,850),(1450,950)])
def test_status_axes_and_inspector_are_readable_without_geometry_mutation(width,height):
    app=QApplication.instance() or QApplication([])
    w=LaunchPlaneWidget(beam_stack=BeamStackDefinition(beams=(BeamDefinition(name='one'),BeamDefinition(name='two',x_um=10))))
    try:
        w.resize(width,height);w.show();app.processEvents()
        contour=((20,0),(0,20),(-20,0),(0,-20))
        text='Host-resolved 1/e input-face footprints. '+ '; '.join(f'Beam {i}: internal angle 30°, captured entrance flux estimate 99.99%' for i in range(8)) + '. Scalar ideal interface; spectral/sampling qualification applies.'
        w.set_resolved_preview([contour,contour],description=text,ray_endpoints=[(100,20),(-100,-20)])
        w.object_list.setCurrentRow(0);w.full_aperture_button.click();app.processEvents()
        assert (w.width(), w.height()) == (width, height)
        assert w.canvas_title.text()=='Input face'
        assert w.x_axis_label.text()=='x (µm)' and w.y_axis_label.text()=='y (µm)'
        assert w.execution_status.text()==text
        assert w.execution_status.height() >= w.execution_status.heightForWidth(w.execution_status.width())
        assert w.status_scroll.horizontalScrollBar().maximum()==0
        assert w.view.height() > 150
        assert w.inspector_scroll.height()>100
        w.inspector_scroll.ensureWidgetVisible(w.derived_k);app.processEvents()
        assert w.derived_k.height() >= w.derived_k.heightForWidth(w.derived_k.width())
        assert w.derived_k.width()>100
        viewport = w.inspector_scroll.viewport()
        value_rect = w.derived_k.rect().translated(
            w.derived_k.mapTo(viewport, w.derived_k.rect().topLeft()))
        assert viewport.rect().contains(value_rect)
        form=w.inspector.layout()
        # Every actual form widget occupies its own nonoverlapping rectangle.
        widgets=[form.itemAt(i).widget() for i in range(form.count()) if form.itemAt(i).widget()]
        assert all(not a.geometry().intersects(b.geometry()) for i,a in enumerate(widgets) for b in widgets[i+1:])
        assert all(item._label.text()==str(i+1) for i,item in enumerate(w.scene.beam_items))
        paths=[item.path() for item in w._resolved_items]
        for action in (w.fit_button.click,w.full_aperture_button.click,lambda:w.object_list.setCurrentRow(1)):
            action();app.processEvents()
            assert [item.path() for item in w._resolved_items]==paths
        first,second=w.scene.beam_items
        assert first._ray_head.zValue()>second._center_marker.zValue()
        assert w.x_axis_label.isVisible() and w.y_axis_label.isVisible()
    finally:
        w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()
