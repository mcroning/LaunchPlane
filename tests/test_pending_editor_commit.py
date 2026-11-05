"""Canonical pending-intent commit and strict Qt correction boundaries."""
import math
from dataclasses import replace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from launchplane.launchpane import LaunchPlaneWidget
from launchplane.model import BeamDefinition, BeamStackDefinition


@pytest.fixture
def editor():
    app = QApplication.instance() or QApplication([])
    w = LaunchPlaneWidget(beam_stack=BeamStackDefinition(beams=(BeamDefinition(),)))
    w.object_list.setCurrentRow(0)
    w.resize(1100,850); w.show(); app.processEvents()
    try:
        yield app,w
    finally:
        w.close();w.deleteLater()
        QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete);app.processEvents()


def test_atomic_commit_uses_qt_values_and_one_normal_model_signal(editor):
    app,w=editor;events=[]
    w.beamStackChanged.connect(events.append)
    w.theta_spin.lineEdit().setText('-30')
    w.w1_spin.lineEdit().setText('25')
    w.power_spin.lineEdit().setText('0.5')
    # Reading a host request recursively must not publish a second mutation.
    w.beamStackChanged.connect(lambda _stack:w.commit_pending_edits())
    w.commit_pending_edits()
    beam=w.beam_stack.beams[0]
    assert (beam.theta_ext_rad,beam.w1_um,beam.power_mW)==(-math.pi/6,25,.5)
    assert len(events)==1
    w.commit_pending_edits()
    assert len(events)==1


def test_invalid_batch_cannot_partially_commit_or_fix_up_to_old_value(editor):
    app,w=editor;before=w.beam_stack
    w.w1_spin.lineEdit().setText('25')
    w.theta_spin.lineEdit().setText('90')
    with pytest.raises(ValueError,match='Invalid pending beam edit: External theta'):
        w.commit_pending_edits()
    assert w.beam_stack==before
    assert w.theta_spin.lineEdit().text()=='90'
    assert w.w1_spin.cleanText()=='25'


@pytest.mark.parametrize('key',[Qt.Key_Tab,Qt.Key_Return])
def test_invalid_pending_text_survives_qt_focus_or_return(editor,key):
    app,w=editor;w.theta_spin.setFocus();app.processEvents()
    w.theta_spin.selectAll();QTest.keyClicks(w.theta_spin,'-')
    assert not w.theta_spin.hasAcceptableInput()
    text=w.theta_spin.text()
    QTest.keyClick(w.theta_spin,key);app.processEvents()
    assert w.theta_spin.text()==text
    with pytest.raises(ValueError,match='Invalid pending beam edit'):
        w.commit_pending_edits()
    assert w.beam_stack.beams[0].theta_ext_rad==0


def test_unchanged_rounded_inspector_does_not_round_model_intent(editor):
    app,w=editor
    beam=replace(w.beam_stack.beams[0],theta_ext_rad=.123456789123,
                 x_um=1.123456789,w1_um=20.123456789)
    w.set_beam_stack(BeamStackDefinition(beams=(beam,)),0)
    w.commit_pending_edits()
    assert w.beam_stack.beams[0]==beam


def _type(app, w, editor, text):
    w.inspector_scroll.ensureWidgetVisible(editor)
    editor.setFocus(); app.processEvents()
    editor.selectAll(); QTest.keyClicks(editor, text)


def test_drafts_follow_beams_across_selection_rebuild_and_multiple_errors(editor):
    app, w = editor
    first = w.beam_stack.beams[0]
    second = replace(first, name='second', x_um=10)
    w.set_beam_stack(BeamStackDefinition(beams=(first, second)), 0)
    _type(app, w, w.theta_spin, '-')
    text = w.theta_spin.text()
    w.object_list.setCurrentRow(1); app.processEvents()
    assert w.theta_spin.hasAcceptableInput()
    _type(app, w, w.w1_spin, '')
    QTest.keyClick(w.w1_spin, Qt.Key_Backspace)
    assert not w.w1_spin.hasAcceptableInput()
    w.object_list.setCurrentRow(0); app.processEvents()
    assert w.theta_spin.text() == text
    for refresh in (w.fit_button.click, w.full_aperture_button.click,
                    lambda: w.resize(1000, 720), w._sync_inspector,
                    lambda: w.set_beam_stack(w.beam_stack, 0)):
        refresh(); app.processEvents()
        assert w.theta_spin.text() == text
    with pytest.raises(ValueError, match='External theta'):
        w.commit_pending_edits()
    _type(app, w, w.theta_spin, '30')
    QTest.keyClick(w.theta_spin, Qt.Key_Return)
    with pytest.raises(ValueError, match='radius w1'):
        w.commit_pending_edits()
    assert w.object_list.currentRow() == 1
    assert not w.w1_spin.hasAcceptableInput()
    _type(app, w, w.w1_spin, '25')
    w.commit_pending_edits()
    assert w.beam_stack.beams[0].theta_ext_rad == math.pi/6
    assert w.beam_stack.beams[1].w1_um == 25
    assert not w._editor_drafts


def test_multiple_invalid_fields_survive_valid_commit_and_sequential_correction(editor):
    app, w = editor
    _type(app, w, w.theta_spin, '-')
    QTest.keyClick(w.theta_spin, Qt.Key_Tab)
    _type(app, w, w.n_ext_spin, '')
    QTest.keyClick(w.n_ext_spin, Qt.Key_Backspace)
    _type(app, w, w.phi_spin, '35')
    QTest.keyClick(w.phi_spin, Qt.Key_Return)
    assert not w.theta_spin.hasAcceptableInput()
    assert not w.n_ext_spin.hasAcceptableInput()
    assert w.beam_stack.beams[0].phi_rad == math.radians(35)
    with pytest.raises(ValueError, match='Invalid pending beam edit'):
        w.commit_pending_edits()
    _type(app, w, w.theta_spin, '30')
    QTest.keyClick(w.theta_spin, Qt.Key_Return)
    with pytest.raises(ValueError, match='External index'):
        w.commit_pending_edits()
    _type(app, w, w.n_ext_spin, '1.2')
    w.commit_pending_edits()
    assert w.beam_stack.beams[0].theta_ext_rad == math.pi/6
    assert w.beam_stack.beams[0].n_ext == 1.2
    assert not w._editor_drafts


def test_draft_ownership_survives_model_replacement_and_rejects_implicit_discard(editor):
    app, w = editor
    _type(app, w, w.theta_spin, '-')
    unresolved = w.theta_spin.text()
    w._beam_moved(0, 4, 5)
    assert w.theta_spin.text() == unresolved
    assert (w.beam_stack.beams[0].x_um, w.beam_stack.beams[0].y_um) == (4, 5)
    w.duplicate_selected()
    assert len(w.beam_stack.beams) == 2
    assert w.theta_spin.hasAcceptableInput()  # New beam has no inherited draft.
    w.object_list.setCurrentRow(0)
    assert w.theta_spin.text() == unresolved
    original = w.beam_stack
    w.delete_selected()
    assert w.beam_stack == original
    assert 'Correct pending beam edits' in w.execution_status.text()
    with pytest.raises(ValueError, match='Unresolved beam edits'):
        w.set_beam_stack(BeamStackDefinition(beams=(BeamDefinition(),)), 0)
    assert w.beam_stack == original and w.theta_spin.text() == unresolved


def test_valid_drafts_on_multiple_beams_publish_one_complete_stack(editor):
    app, w = editor
    first = w.beam_stack.beams[0]
    second = replace(first, name='second')
    w.set_beam_stack(BeamStackDefinition(beams=(first, second)), 0)
    # Model-to-widget selection refresh may happen before a focus commit.
    w.theta_spin.lineEdit().setText('30')
    w.object_list.setCurrentRow(1)
    w.w1_spin.lineEdit().setText('25')
    events = []
    def observe(stack):
        w.commit_pending_edits()  # Synchronous host reentry sees the whole stack.
        events.append(w.beam_stack)
    w.beamStackChanged.connect(observe)
    w.commit_pending_edits()
    assert len(events) == 1
    assert events[0].beams[0].theta_ext_rad == math.pi/6
    assert events[0].beams[1].w1_um == 25
    assert w.object_list.currentRow() == 1


def test_explicit_correction_to_original_value_clears_draft(editor):
    app, w = editor
    _type(app, w, w.theta_spin, '-')
    QTest.keyClick(w.theta_spin, Qt.Key_Tab)
    _type(app, w, w.phi_spin, '35')
    QTest.keyClick(w.phi_spin, Qt.Key_Return)
    assert w._editor_drafts
    _type(app, w, w.theta_spin, '0')
    QTest.keyClick(w.theta_spin, Qt.Key_Return)
    w.commit_pending_edits()
    assert not w._editor_drafts
    assert w.beam_stack.beams[0].theta_ext_rad == 0
    assert w.beam_stack.beams[0].phi_rad == math.radians(35)
