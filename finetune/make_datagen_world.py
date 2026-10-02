#!/usr/bin/env python3
"""Build worlds/datagen.sdf from worlds/default.sdf for YOLO dataset capture.

Adds to every traffic vehicle / pedestrian a Label plugin holding its COCO
class id + 1 (label 0 is avoided), and a static 'datacam' model carrying an
RGB camera and a 2D bounding-box camera with the same optics as the drone's
IMX214 (1920x1080, hfov 1.204 rad).

Usage: python3 finetune/make_datagen_world.py
"""

import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', 'worlds', 'default.sdf')
DST = os.path.join(HERE, '..', 'worlds', 'datagen.sdf')

# model uri -> COCO class id
COCO_ID = {
    'casual_female': 0,  # person
    'hatchback': 2, 'hatchback_blue': 2, 'hatchback_red': 2, 'suv': 2,  # car
    'motorbike_red': 3, 'motorbike_blue': 3,
    'motorbike_black': 3, 'motorbike_white': 3,  # motorcycle
    'bus': 5,  # bus
    'pickup': 7,  # truck
}

CAMERA = '''    <model name='datacam'>
      <static>true</static>
      <pose>273.6 -143.2 20 0 0.8 -0.7</pose>
      <link name='link'>
        <sensor name='rgb' type='camera'>
          <camera>
            <horizontal_fov>1.204</horizontal_fov>
            <image><width>1920</width><height>1080</height></image>
            <clip><near>0.1</near><far>100</far></clip>
          </camera>
          <always_on>1</always_on>
          <update_rate>5</update_rate>
          <topic>datacam/image</topic>
        </sensor>
        <sensor name='boxes' type='boundingbox_camera'>
          <camera>
            <box_type>2d</box_type>
            <horizontal_fov>1.204</horizontal_fov>
            <image><width>1920</width><height>1080</height></image>
            <clip><near>0.1</near><far>100</far></clip>
          </camera>
          <always_on>1</always_on>
          <update_rate>5</update_rate>
          <topic>datacam/boxes</topic>
        </sensor>
      </link>
    </model>
'''


def add_label(match):
    block = match.group(0)
    uri = re.search(r'<uri>model://([^<]+)</uri>', block).group(1)
    if uri not in COCO_ID:
        return block
    plugin = ('      <plugin filename="gz-sim-label-system" name="gz::sim::systems::Label">'
              f'<label>{COCO_ID[uri] + 1}</label></plugin>\n')
    return block.replace('    </include>', plugin + '    </include>')


def main():
    sdf = open(SRC).read()
    sdf = re.sub(r'    <include>.*?    </include>', add_label, sdf, flags=re.S)
    sdf = sdf.replace('  </world>', CAMERA + '  </world>')
    open(DST, 'w').write(sdf)
    print(f'wrote {os.path.normpath(DST)} ({sdf.count("gz-sim-label-system")} labelled models)')


if __name__ == '__main__':
    main()
