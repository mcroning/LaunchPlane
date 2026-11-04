"""Offscreen editor-only checks; no host, launch resolver or physical sampling."""
import os, unittest
from types import SimpleNamespace
from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit
from PySide6.QtGui import QValidator
from launchplane.launchpane import IntentSpinBox, LaunchPlaneWidget
from launchplane.model import BeamDefinition, BeamStackDefinition
from launchplane.serialization import beam_stack_to_dict, beam_stack_from_dict

class CompactIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert os.environ['QT_QPA_PLATFORM']=='offscreen'
        cls.app=QApplication.instance() or QApplication(['intent-display-only'])

    def editor(self, decimals=6, value=1.234567, suffix=' µm'):
        w=QWidget();layout=QVBoxLayout(w)
        # Calling the editor factory has no model/preview side effects.
        e=LaunchPlaneWidget._create_spin_box(w,-1e6,1e6,decimals,suffix)
        e.setValue(value);other=QLineEdit();layout.addWidget(e);layout.addWidget(other)
        w.show();other.setFocus();self.app.processEvents();self.addCleanup(w.close)
        return e,other

    def test_compact_focus_roundtrip_and_signal_fidelity(self):
        for decimals,value in ((3,12345.678),(4,12345.6789),(6,1.234567),(6,-89.123456),(6,.000001)):
            with self.subTest(decimals=decimals,value=value):
                e,other=self.editor(decimals,value)
                identity=(e.value(),e.decimals(),e.minimum(),e.maximum(),e.singleStep(),e.suffix())
                signals=[];e.valueChanged.connect(signals.append)
                self.assertEqual(e.lineEdit().text(),format(value,'.6g')+e.suffix())
                self.assertEqual(e.valueFromText(e.lineEdit().text()),value)
                e.interpretText();self.assertEqual(e.value(),value)
                for _ in range(3):
                    e.setFocus();self.app.processEvents()
                    self.assertIn(f'{value:.{decimals}f}',e.lineEdit().text())
                    other.setFocus();self.app.processEvents()
                    self.assertEqual(e.value(),value)
                self.assertEqual(signals,[])
                self.assertEqual(identity,(e.value(),e.decimals(),e.minimum(),e.maximum(),e.singleStep(),e.suffix()))
                margins=e.lineEdit().textMargins()
                e.setFocus();self.app.processEvents()
                self.assertLessEqual(e.lineEdit().fontMetrics().horizontalAdvance(e.lineEdit().text()),e.lineEdit().contentsRect().width()-margins.left()-margins.right()-4)

    def test_invalid_and_pending_drafts_not_overwritten(self):
        e,other=self.editor()
        e.setFocus();self.app.processEvents()
        e.lineEdit().setText('-')
        self.assertFalse(e.hasAcceptableInput())
        other.setFocus();self.app.processEvents()
        self.app.sendEvent(e,QEvent(QEvent.Hide));e.setFocus();self.app.processEvents()
        self.assertEqual(e.lineEdit().text().removesuffix(e.suffix()),'-');self.assertEqual(e.value(),1.234567)
        owner=object()
        fixture=SimpleNamespace(_updating_inspector=False,_editor_owner=owner,
            _numeric_editors={'x_um':e},_angular_editors={},_editor_drafts={})
        LaunchPlaneWidget._capture_pending_edits(fixture)
        self.assertEqual(fixture._editor_drafts[id(owner)][1],{'x_um':e.lineEdit().text()})
        e.lineEdit().setText('2.345678 µm')
        LaunchPlaneWidget._capture_pending_edits(fixture)
        self.assertEqual(fixture._editor_drafts[id(owner)][1],{'x_um':'2.345678 µm'})
        e.interpretText();self.assertEqual(e.value(),2.345678)
        other.setFocus();self.app.processEvents()
        LaunchPlaneWidget._capture_pending_edits(fixture)
        self.assertNotIn(id(owner),fixture._editor_drafts)

    def test_explicit_compact_token_is_an_edit_not_a_roundtrip(self):
        e,other=self.editor()
        e.setFocus();self.app.processEvents()
        e.lineEdit().setText('1.23457 µm')
        other.setFocus();self.app.processEvents()
        self.assertEqual(e.value(),1.23457)

    def test_value_edit_step_and_schema_precision(self):
        e,other=self.editor()
        signals=[];e.valueChanged.connect(signals.append)
        e.setFocus();self.app.processEvents();e.lineEdit().setText('1.765432 µm');e.interpretText()
        self.assertEqual(e.value(),1.765432);self.assertEqual(signals,[1.765432])
        before=e.value();step=e.singleStep();e.stepUp();self.assertAlmostEqual(e.value(),before+step,places=6)
        stack=BeamStackDefinition(beams=(BeamDefinition(wavelength_um=1.765432),))
        payload=beam_stack_to_dict(stack)
        self.assertEqual(payload['schema_version'],4)
        self.assertEqual(beam_stack_from_dict(payload),stack)

if __name__=='__main__':unittest.main()
