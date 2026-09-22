import json
from dataclasses import fields
import pytest
from launchplane.model import BeamDefinition, BeamStackDefinition
from launchplane.serialization import (beam_stack_to_dict,beam_stack_from_dict,
    save_beam_stack_json,load_beam_stack_json,SCHEMA_VERSION)


def example():
    return BeamStackDefinition(beams=(BeamDefinition(name='asymmetric',wavelength_um=.532,
        power_mW=2.3,n_ext=1.4,theta_ext_rad=.8,phi_rad=2.1,w1_um=3,w2_um=8,
        psi_rad=.7,x_um=5,y_um=-6,phase_rad=1.2,enabled=False,coherence_group='laser B'),))


def test_roundtrip_all_physical_intent_and_derived_values(tmp_path):
    stack=example(); data=beam_stack_to_dict(stack)
    assert SCHEMA_VERSION==4
    assert set(data['beams'][0])=={f.name for f in fields(BeamDefinition)}
    assert not any('tilt' in k or 'wavevector' in k for k in data['beams'][0])
    restored=beam_stack_from_dict(json.loads(json.dumps(data)))
    assert restored==stack
    assert restored.beams[0].external_wavevector_rad_per_um==stack.beams[0].external_wavevector_rad_per_um
    p=save_beam_stack_json(stack,tmp_path/'nested'/'beams.json')
    assert load_beam_stack_json(p)==stack
    assert beam_stack_to_dict(restored)==data


@pytest.mark.parametrize('version',[None,1,2,3,5,'4',4.0,True])
def test_obsolete_or_unknown_schema_rejected_without_guessing(version):
    with pytest.raises(ValueError,match='Recreate/re-export'):
        beam_stack_from_dict({'schema_version':version,'beams':[]})


@pytest.mark.parametrize('name',[f.name for f in fields(BeamDefinition)])
def test_missing_intent_not_silently_defaulted(name):
    data=beam_stack_to_dict(example());del data['beams'][0][name]
    with pytest.raises(ValueError,match='schema-4 fields'): beam_stack_from_dict(data)


def test_unknown_derived_or_old_fields_rejected():
    for key in ('tilt_x_rad_per_um','kx','launch_input_mode','focus_z_um'):
        data=beam_stack_to_dict(example());data['beams'][0][key]=0
        with pytest.raises(ValueError,match='unexpected'): beam_stack_from_dict(data)


@pytest.mark.parametrize('payload',[[],{'schema_version':4,'beams':{}}, {'schema_version':4,'beams':[1]},
                                   {'schema_version':4,'beams':[],'unknown':1}])
def test_malformed_payload(payload):
    with pytest.raises((TypeError,ValueError)):beam_stack_from_dict(payload)


def test_invalid_json_and_physical_values(tmp_path):
    p=tmp_path/'bad.json';p.write_text('{')
    with pytest.raises(ValueError,match='Invalid JSON'):load_beam_stack_json(p)
    data=beam_stack_to_dict(example());data['beams'][0]['n_ext']=0
    with pytest.raises(ValueError,match='n_ext'):beam_stack_from_dict(data)


def test_empty_stack_roundtrip():
    assert beam_stack_from_dict(beam_stack_to_dict(BeamStackDefinition()))==BeamStackDefinition()
