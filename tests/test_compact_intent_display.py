"""Offscreen editor-only checks; no host, launch resolver or physical sampling."""
import os, unittest
from types import SimpleNamespace
from PySide6.QtCore import QEvent, Qt, QLocale
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout, QLineEdit, QDoubleSpinBox
from PySide6.QtGui import QValidator
from launchplane.launchpane import IntentSpinBox, LaunchPlaneWidget
from launchplane.model import BeamDefinition, BeamStackDefinition
from launchplane.serialization import beam_stack_to_dict, beam_stack_from_dict

class CompactIntentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert os.environ['QT_QPA_PLATFORM']=='offscreen'
        cls.app=QApplication.instance() or QApplication(['intent-display-only'])

    def editor(self, decimals=6, value=1.234567, suffix=' µm', *, locale='C', maximum=1e6):
        w=QWidget();layout=QVBoxLayout(w)
        # Calling the editor factory has no model/preview side effects.
        e=LaunchPlaneWidget._create_spin_box(w,-maximum,maximum,decimals,suffix)
        e.setLocale(QLocale(locale))
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



    def test_locale_display_focus_and_sizing_preserve_exact_values(self):
        for locale in ('C','de_DE','fr_FR'):
            for decimals,value,maximum in ((6,1.234567,1e6),(6,-89.123456,1e6),
                    (6,.000001,1e6),(6,.000012,1e6),(4,123456789.1234,1e9)):
                with self.subTest(locale=locale,value=value):
                    e,other=self.editor(decimals,value,locale=locale,maximum=maximum)
                    original=(e.value(),e.decimals(),e.minimum(),e.maximum(),e.singleStep())
                    options=e.locale().numberOptions()
                    compact=e.locale();compact.setNumberOptions(options|QLocale.OmitGroupSeparator)
                    expected=compact.toString(value,'g',6)+e.suffix()
                    self.assertEqual(e.text(),expected)
                    self.assertEqual(e.validate(expected,0)[0],QValidator.Acceptable)
                    self.assertEqual(e.valueFromText(expected),value)
                    e.interpretText();self.assertEqual(e.value(),value)
                    changes=[];e.valueChanged.connect(changes.append)
                    for _ in range(3):
                        e.setFocus();self.app.processEvents()
                        self.assertEqual(e.text(),QDoubleSpinBox.textFromValue(e,value)+e.suffix())
                        margins=e.lineEdit().textMargins()
                        self.assertLessEqual(e.fontMetrics().horizontalAdvance(e.text()),
                            e.lineEdit().contentsRect().width()-margins.left()-margins.right()-4)
                        other.setFocus();self.app.processEvents()
                        self.assertEqual(e.text(),expected);self.assertEqual(e.value(),value)
                    self.assertEqual(changes,[])
                    self.assertEqual(original,(e.value(),e.decimals(),e.minimum(),e.maximum(),e.singleStep()))
                    self.assertEqual(e.locale().numberOptions(),options)

    def test_locale_explicit_compact_edits_and_steps(self):
        for locale in ('C','de_DE','fr_FR'):
            for decimals,value,maximum in ((6,1.234567,1e6),(6,.000001,1e6),
                                          (4,123456789.1234,1e9)):
                with self.subTest(locale=locale,value=value):
                    e,other=self.editor(decimals,value,locale=locale,maximum=maximum)
                    token=e.text();parsed,ok=e.locale().toDouble(token.removesuffix(e.suffix()))
                    self.assertTrue(ok)
                    changes=[];e.valueChanged.connect(changes.append)
                    # An unfocused step must start from the exact stored value.
                    e.stepUp();self.assertEqual(e.value(),round(value+e.singleStep(),decimals))
                    e.stepDown();self.assertEqual(e.value(),value)
                    changes.clear()
                    e.setFocus();self.app.processEvents();e.lineEdit().setText(token)
                    self.assertEqual(e.validate(token,0)[0],QValidator.Acceptable)
                    self.assertEqual(e.valueFromText(token),parsed)
                    other.setFocus();self.app.processEvents()
                    self.assertEqual(e.value(),parsed)
                    self.assertEqual(changes,[parsed] if parsed!=value else [])
                    before=e.value();e.stepUp()
                    self.assertEqual(e.value(),round(before+e.singleStep(),decimals))
                    stack=BeamStackDefinition(beams=(BeamDefinition(power_mW=e.value()),))
                    self.assertEqual(beam_stack_from_dict(beam_stack_to_dict(stack)),stack)

    def test_locale_exponents_validation_and_draft_ownership(self):
        for locale in ('de_DE','fr_FR'):
            for text,value in (('2,3e-05',.000023),('1,23457e+07',12345700.0)):
                with self.subTest(locale=locale,text=text):
                    e,other=self.editor(locale=locale,maximum=1e9)
                    owner=object();fixture=SimpleNamespace(_updating_inspector=False,
                        _editor_owner=owner,_numeric_editors={'power_mW':e},
                        _angular_editors={},_editor_drafts={})
                    e.setFocus();self.app.processEvents()
                    draft=text+e.suffix();e.lineEdit().setText(draft)
                    self.assertEqual(e.validate(draft,0)[0],QValidator.Acceptable)
                    self.assertEqual(e.valueFromText(draft),value)
                    LaunchPlaneWidget._capture_pending_edits(fixture)
                    self.assertEqual(fixture._editor_drafts[id(owner)][1],{'power_mW':draft})
                    signals=[];e.valueChanged.connect(signals.append)
                    e.interpretText();self.assertEqual(e.value(),value);self.assertEqual(signals,[value])
                    other.setFocus();self.app.processEvents()
                    LaunchPlaneWidget._capture_pending_edits(fixture)
                    self.assertNotIn(id(owner),fixture._editor_drafts)
                    for invalid in ('1e-','1,234567e-06','1e+10','1.2e-05'):
                        e.setFocus();self.app.processEvents()
                        bad=invalid+e.suffix();e.lineEdit().setText(bad)
                        self.assertNotEqual(e.validate(bad,0)[0],QValidator.Acceptable)
                        LaunchPlaneWidget._capture_pending_edits(fixture)
                        self.assertEqual(fixture._editor_drafts[id(owner)][1],{'power_mW':bad})
                        other.setFocus();self.app.processEvents()
                        self.app.sendEvent(e,QEvent(QEvent.Hide));e.setFocus();self.app.processEvents()
                        self.assertEqual(e.lineEdit().text(),bad)
                        self.assertEqual(e.value(),value)

    def test_locale_grouping_matches_qt_and_does_not_mutate_locale(self):
        for locale in ('de_DE','fr_FR'):
            e,other=self.editor(4,12345.6789,locale=locale)
            options=e.locale().numberOptions();e.setGroupSeparatorShown(True)
            self.app.processEvents()
            expected=e.locale().toString(e.value(),'g',6)+e.suffix()
            self.assertEqual(e.text(),expected)
            self.assertIn(e.locale().groupSeparator(),expected)
            self.assertEqual(e.valueFromText(expected),12345.6789)
            e.setFocus();self.app.processEvents()
            self.assertEqual(e.text(),QDoubleSpinBox.textFromValue(e,e.value())+e.suffix())
            margins=e.lineEdit().textMargins()
            self.assertLessEqual(e.fontMetrics().horizontalAdvance(e.text()),
                e.lineEdit().contentsRect().width()-margins.left()-margins.right()-4)
            other.setFocus();self.app.processEvents()
            self.assertEqual(e.value(),12345.6789)
            self.assertEqual(e.locale().numberOptions(),options)
            e.setGroupSeparatorShown(False);self.app.processEvents()
            self.assertNotIn(e.locale().groupSeparator(),e.cleanText())

if __name__=='__main__':unittest.main()
