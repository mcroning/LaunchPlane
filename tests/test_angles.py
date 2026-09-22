"""Physical external intent, independent of Qt and the material resolver."""
import math
from dataclasses import replace
import pytest
from launchplane.model import BeamDefinition, BeamStackDefinition, LaunchPlaneDefinition


def test_normal_direction_and_default_medium():
    beam = BeamDefinition(phi_rad=1.7)
    assert beam.external_direction == (0, 0, 1)
    assert beam.transverse_wavevector_rad_per_um == (0, 0)
    assert beam.n_ext == 1


@pytest.mark.parametrize('phi,xy', [(0,(1,0)), (math.pi/2,(0,1)),
                                    (math.pi,(-1,0)), (3*math.pi/2,(0,-1))])
def test_quadrants(phi, xy):
    beam = BeamDefinition(theta_ext_rad=math.pi/6, phi_rad=phi, n_ext=1.5, wavelength_um=0.5)
    assert beam.external_direction == pytest.approx((xy[0]/2,xy[1]/2,math.sqrt(3)/2))
    assert beam.transverse_wavevector_rad_per_um == pytest.approx((3*math.pi*xy[0],3*math.pi*xy[1]))


def test_arbitrary_direction_and_independent_roll():
    beam = BeamDefinition(theta_ext_rad=0.7, phi_rad=0.8, w1_um=3, w2_um=7,
                          psi_rad=0.4, x_um=5, y_um=-6, phase_rad=1.2)
    expected=(math.sin(.7)*math.cos(.8), math.sin(.7)*math.sin(.8), math.cos(.7))
    assert beam.external_direction == expected
    assert replace(beam, psi_rad=1.9).external_wavevector_rad_per_um == beam.external_wavevector_rad_per_um
    assert replace(beam, wavelength_um=2*beam.wavelength_um).external_wavevector_rad_per_um == pytest.approx(tuple(k/2 for k in beam.external_wavevector_rad_per_um))
    assert replace(beam, n_ext=2).external_wavevector_rad_per_um == pytest.approx(tuple(k*2 for k in beam.external_wavevector_rad_per_um))
    assert (beam.x_um,beam.y_um,beam.phase_rad,beam.w1_um,beam.w2_um)==(5,-6,1.2,3,7)


def test_angle_wrapping_and_immutable_equality():
    a=BeamDefinition(phi_rad=-math.pi/2,psi_rad=math.tau)
    b=BeamDefinition(phi_rad=3*math.pi/2,psi_rad=0)
    assert a==b and hash(a)==hash(b)
    with pytest.raises(AttributeError):
        a.n_ext=2


@pytest.mark.parametrize('field,value', [
    ('theta_ext_rad',-1e-9), ('theta_ext_rad',math.pi/2), ('theta_ext_rad',math.pi),
    ('n_ext',0), ('n_ext',-1), ('n_ext',math.inf), ('n_ext',math.nan),
    ('w1_um',0), ('w2_um',-1), ('wavelength_um',0), ('power_mW',-1),
    ('phi_rad',math.nan), ('psi_rad',math.inf), ('x_um',math.nan),
    ('phase_rad',math.inf), ('enabled',1), ('power_mW',True),
    ('name',''), ('coherence_group',' '), ('profile','focused_gaussian'),
    ('profile','uniform'), ('profile','legacy_gaussian'),
])
def test_invalid_intent_rejected(field,value):
    with pytest.raises(ValueError): BeamDefinition(**{field:value})


def test_old_constructor_is_not_an_execution_bridge():
    with pytest.raises(TypeError): BeamDefinition(waist_x_um=3)
    with pytest.raises(TypeError): BeamDefinition(tilt_x_rad_per_um=0.2)
    with pytest.raises(TypeError): BeamDefinition(launch_input_mode='angle')
    assert not hasattr(BeamDefinition(), 'waist_x_um')
    assert not hasattr(BeamDefinition(), 'tilt_x_rad_per_um')


def test_stack_power_groups_and_names():
    stack=BeamStackDefinition(beams=[BeamDefinition(name='a',power_mW=0),
        BeamDefinition(name='b',power_mW=2),BeamDefinition(name='c',power_mW=9,enabled=False,coherence_group='other')])
    assert stack.total_power_mW==2
    assert stack.coherence_groups==('laser_A','other')
    assert isinstance(stack.beams,tuple)
    with pytest.raises(ValueError,match='Duplicate'): BeamStackDefinition(beams=(BeamDefinition(),BeamDefinition()))


@pytest.mark.parametrize('value',[0,-1,math.nan,math.inf])
def test_aperture_validation(value):
    with pytest.raises(ValueError): LaunchPlaneDefinition(x_aperture_um=value)


def test_model_and_serialization_are_headless():
    import subprocess
    import sys
    subprocess.run([sys.executable, '-c',
        'import sys; from launchplane.model import BeamDefinition; '
        'from launchplane.serialization import beam_stack_to_dict; '
        'BeamDefinition(); assert not any(m.startswith("PySide6") for m in sys.modules)'],
        check=True)
