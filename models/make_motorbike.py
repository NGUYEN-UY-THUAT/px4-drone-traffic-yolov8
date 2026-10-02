#!/usr/bin/env python3
"""Generate simple motorbike-with-rider models (primitive shapes) for Gazebo.

Fuel has no motorcycle model, so this builds an underbone-style scooter
(like the ones common in Vietnamese traffic) out of boxes, cylinders and
spheres. Model frame: +x forward, +z up, origin on the ground.

Usage: python3 make_motorbike.py   (writes models/motorbike_<color>/)
"""

import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# name: (body rgb, rider shirt rgb, helmet rgb)
VARIANTS = {
    'motorbike_red': ((0.75, 0.05, 0.05), (0.15, 0.25, 0.60), (0.95, 0.95, 0.95)),
    'motorbike_blue': ((0.05, 0.20, 0.70), (0.85, 0.85, 0.85), (0.90, 0.10, 0.10)),
    'motorbike_black': ((0.08, 0.08, 0.08), (0.80, 0.55, 0.15), (0.10, 0.30, 0.80)),
    'motorbike_white': ((0.90, 0.90, 0.90), (0.20, 0.50, 0.20), (0.20, 0.20, 0.20)),
}

TIRE = (0.05, 0.05, 0.05)
METAL = (0.60, 0.60, 0.62)
SEAT = (0.12, 0.10, 0.08)
SKIN = (0.85, 0.65, 0.50)
PANTS = (0.15, 0.15, 0.20)


def material(rgb):
    c = f'{rgb[0]} {rgb[1]} {rgb[2]} 1'
    return (f'<material><ambient>{c}</ambient><diffuse>{c}</diffuse>'
            f'<specular>0.2 0.2 0.2 1</specular></material>')


def visual(name, pose, geom, rgb):
    return (f'      <visual name="{name}">\n'
            f'        <pose>{" ".join(f"{v:.4f}" for v in pose)}</pose>\n'
            f'        <geometry>{geom}</geometry>\n'
            f'        {material(rgb)}\n'
            f'      </visual>\n')


def box(name, xyz, size, rgb, rpy=(0, 0, 0)):
    return visual(name, (*xyz, *rpy), f'<box><size>{size[0]} {size[1]} {size[2]}</size></box>', rgb)


def cyl(name, xyz, radius, length, rgb, rpy=(0, 0, 0)):
    return visual(name, (*xyz, *rpy),
                  f'<cylinder><radius>{radius}</radius><length>{length}</length></cylinder>', rgb)


def sphere(name, xyz, radius, rgb):
    return visual(name, (*xyz, 0, 0, 0), f'<sphere><radius>{radius}</radius></sphere>', rgb)


def rod(name, p0, p1, radius, rgb):
    """Cylinder spanning from point p0 to point p1."""
    d = [b - a for a, b in zip(p0, p1)]
    length = math.sqrt(sum(v * v for v in d))
    mid = [(a + b) / 2 for a, b in zip(p0, p1)]
    # Rotate the cylinder's z axis onto d: pitch about y, then yaw about z
    pitch = math.acos(d[2] / length)
    yaw = math.atan2(d[1], d[0])
    return cyl(name, mid, radius, length, rgb, (0, pitch, yaw))


def build(body, shirt, helmet):
    v = ''
    # Wheels (axis along y)
    for tag, x in (('rear', -0.62), ('front', 0.62)):
        v += cyl(f'{tag}_tire', (x, 0, 0.28), 0.28, 0.10, TIRE, (math.pi / 2, 0, 0))
        v += cyl(f'{tag}_rim', (x, 0, 0.28), 0.17, 0.11, METAL, (math.pi / 2, 0, 0))
    # Front fork, cowl, headlight, handlebar
    v += rod('fork_l', (0.62, 0.07, 0.28), (0.40, 0.07, 0.95), 0.025, METAL)
    v += rod('fork_r', (0.62, -0.07, 0.28), (0.40, -0.07, 0.95), 0.025, METAL)
    v += box('front_fender', (0.62, 0, 0.60), (0.40, 0.14, 0.05), body)
    v += box('front_cowl', (0.40, 0, 0.78), (0.22, 0.34, 0.45), body, (0, -0.35, 0))
    v += box('headlight_housing', (0.40, 0, 1.03), (0.20, 0.30, 0.16), body)
    v += cyl('headlight', (0.51, 0, 1.03), 0.06, 0.03, (1.0, 1.0, 0.85), (0, math.pi / 2, 0))
    v += cyl('handlebar', (0.34, 0, 1.06), 0.02, 0.72, METAL, (math.pi / 2, 0, 0))
    v += cyl('grip_l', (0.34, 0.33, 1.06), 0.03, 0.12, TIRE, (math.pi / 2, 0, 0))
    v += cyl('grip_r', (0.34, -0.33, 1.06), 0.03, 0.12, TIRE, (math.pi / 2, 0, 0))
    for side, y in (('l', 0.26), ('r', -0.26)):
        v += rod(f'mirror_stem_{side}', (0.34, y, 1.06), (0.30, y * 1.1, 1.28), 0.01, METAL)
        v += box(f'mirror_{side}', (0.30, y * 1.1, 1.30), (0.02, 0.10, 0.07), TIRE)
    # Frame, floorboard, engine, rear body, seat, tail
    v += box('floorboard', (0.05, 0, 0.42), (0.55, 0.30, 0.06), body)
    v += box('frame_tube', (0.20, 0, 0.62), (0.35, 0.14, 0.12), body, (0, 0.6, 0))
    v += box('engine', (-0.25, 0, 0.32), (0.45, 0.26, 0.28), METAL)
    v += box('rear_body', (-0.38, 0, 0.66), (0.80, 0.34, 0.30), body)
    v += box('seat', (-0.35, 0, 0.855), (0.75, 0.30, 0.09), SEAT)
    v += box('rear_fender', (-0.78, 0, 0.62), (0.30, 0.16, 0.05), body)
    v += box('taillight', (-0.79, 0, 0.72), (0.04, 0.16, 0.06), (0.9, 0.05, 0.05))
    v += rod('exhaust', (-0.10, -0.18, 0.28), (-0.80, -0.18, 0.40), 0.045, METAL)
    # Rider sitting on the seat, hands on the grips
    v += box('pelvis', (-0.32, 0, 0.95), (0.25, 0.34, 0.14), PANTS)
    v += box('torso', (-0.24, 0, 1.24), (0.22, 0.40, 0.52), shirt, (0, 0.25, 0))
    v += sphere('neck', (-0.16, 0, 1.52), 0.06, SKIN)
    v += sphere('head', (-0.14, 0, 1.64), 0.12, SKIN)
    v += sphere('helmet', (-0.15, 0, 1.68), 0.135, helmet)
    for side, y in (('l', 1), ('r', -1)):
        shoulder = (-0.17, 0.19 * y, 1.44)
        elbow = (0.07, 0.27 * y, 1.20)
        hand = (0.33, 0.33 * y, 1.07)
        hip = (-0.30, 0.11 * y, 0.95)
        knee = (0.05, 0.19 * y, 0.95)
        foot = (0.10, 0.12 * y, 0.50)
        v += rod(f'upper_arm_{side}', shoulder, elbow, 0.05, shirt)
        v += rod(f'forearm_{side}', elbow, hand, 0.04, SKIN)
        v += rod(f'thigh_{side}', hip, knee, 0.07, PANTS)
        v += rod(f'shin_{side}', knee, foot, 0.055, PANTS)
        v += box(f'shoe_{side}', (0.15, 0.12 * y, 0.48), (0.22, 0.10, 0.07), TIRE)
    return v


def main():
    for name, (body, shirt, helmet) in VARIANTS.items():
        d = os.path.join(HERE, name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, 'model.sdf'), 'w') as f:
            f.write('<?xml version="1.0" ?>\n<sdf version="1.6">\n'
                    f'  <model name="{name}">\n    <static>true</static>\n'
                    '    <link name="link">\n'
                    '      <collision name="collision">\n'
                    '        <pose>0 0 0.5 0 0 0</pose>\n'
                    '        <geometry><box><size>1.8 0.7 1.0</size></box></geometry>\n'
                    '      </collision>\n'
                    f'{build(body, shirt, helmet)}'
                    '    </link>\n  </model>\n</sdf>\n')
        with open(os.path.join(d, 'model.config'), 'w') as f:
            f.write('<?xml version="1.0"?>\n<model>\n'
                    f'  <name>{name}</name>\n  <version>1.0</version>\n'
                    '  <sdf version="1.6">model.sdf</sdf>\n'
                    '  <description>Primitive motorbike with rider, generated by make_motorbike.py</description>\n'
                    '</model>\n')
        print('wrote', d)


if __name__ == '__main__':
    main()
