#!/usr/bin/env python3
"""Capture an auto-labelled YOLO dataset from worlds/datagen.sdf.

For every sample the traffic vehicles and pedestrians are scattered on the
road, the 'datacam' camera is placed at a random altitude / gimbal pitch /
heading looking at the road, and the RGB frame is saved together with the
2D boxes from the bounding-box camera (Label plugin value = COCO id + 1).

Run with the system python3 (gz-transport bindings) while
`gz sim -s -r worlds/datagen.sdf` is running (GZ_IP=127.0.0.1):

    python3 finetune/collect.py --out finetune/data --n 2000 --seed 0
"""

import argparse
import math
import os
import random
import subprocess
import sys
import threading
import time

import cv2
import numpy as np
from gz.transport13 import Node
from gz.msgs10.annotated_axis_aligned_2d_box_v_pb2 import AnnotatedAxisAligned2DBox_V
from gz.msgs10.image_pb2 import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from traffic import ALONG, LANES, NORMAL, ORIGIN, S_MAX, S_MIN, VEHICLES, height  # noqa: E402

PEDESTRIANS = ['casual_female_1', 'casual_female_2']
MIN_BOX_PX = 6       # drop boxes smaller than this (width or height)
VAL_FRACTION = 0.15


def quat(roll, pitch, yaw):
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return (sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy, cr * cp * cy + sr * sp * sy)


def road_xy(s, lat):
    return (ORIGIN[0] + s * ALONG[0] + lat * NORMAL[0],
            ORIGIN[1] + s * ALONG[1] + lat * NORMAL[1])


ROAD_YAW = math.atan2(ALONG[1], ALONG[0])


def scatter_traffic():
    """Random positions on the road for every vehicle and pedestrian.
    Returns the poses and the road coordinate of a 'focus' point."""
    poses, taken = [], []
    for name, lane, _, length in VEHICLES:
        bike = name.startswith('motorbike')
        for _ in range(30):
            if bike and random.random() < 0.3:
                lat = random.uniform(-4.0, 8.0)  # bikes weave across lanes
            else:
                lat = LANES[lane][0] + random.uniform(-0.6, 0.6)
            s = random.uniform(S_MIN, S_MAX)
            if all(abs(s - ts) > (length + tl) / 2 + 0.5 or abs(lat - tlat) > 2.0
                   for ts, tlat, tl in taken):
                break
        taken.append((s, lat, length))
        direction = LANES[lane][1] if random.random() < 0.9 else -LANES[lane][1]
        yaw = ROAD_YAW + (0.0 if direction > 0 else math.pi) + random.gauss(0, 0.08)
        x, y = road_xy(s, lat)
        poses.append((name, (x, y, height(s)), quat(0, 0, yaw)))
    for name in PEDESTRIANS:
        s, lat = random.uniform(S_MIN, S_MAX), random.choice([-6.0, -5.5, 9.5, 10.0, random.uniform(-4, 8)])
        x, y = road_xy(s, lat)
        poses.append((name, (x, y, height(s)), quat(0, 0, random.uniform(-math.pi, math.pi))))
    # Focus on a random vehicle, biased towards motorbikes
    bikes = [t for t, (n, *_) in zip(taken, VEHICLES) if n.startswith('motorbike')]
    s, lat, _ = random.choice(bikes if random.random() < 0.6 else taken)
    return poses, s, lat


def camera_pose(s, lat):
    """Drone-like viewpoint looking at road point (s, lat)."""
    alt = random.uniform(4.0, 35.0)                 # metres above the road
    pitch = random.uniform(math.radians(25), math.radians(90))
    yaw = ROAD_YAW + random.choice([0, math.pi]) + random.gauss(0, 0.6)
    if random.random() < 0.3:
        yaw = random.uniform(-math.pi, math.pi)
    # Aim near the focus point, not always dead centre
    s += random.uniform(-6, 6)
    lat += random.uniform(-3, 3)
    tx, ty = road_xy(s, lat)
    tz = height(s)
    ground = alt / math.tan(pitch) if pitch < math.radians(89) else 0.0
    x = tx - ground * math.cos(yaw)
    y = ty - ground * math.sin(yaw)
    roll = random.gauss(0, 0.03)
    return ('datacam', (x, y, tz + alt), quat(roll, pitch, yaw))


class Capture:
    def __init__(self):
        self.lock = threading.Lock()
        self.imgs, self.boxes = {}, {}
        self.node = Node()
        self.node.subscribe(Image, '/datacam/image', self._img)
        self.node.subscribe(AnnotatedAxisAligned2DBox_V, '/datacam/boxes', self._box)

    @staticmethod
    def _stamp(h):
        return h.stamp.sec * 10**9 + h.stamp.nsec

    def _img(self, m):
        with self.lock:
            self.imgs[self._stamp(m.header)] = m
            for k in sorted(self.imgs)[:-10]:
                del self.imgs[k]

    def _box(self, m):
        with self.lock:
            self.boxes[self._stamp(m.header)] = m
            for k in sorted(self.boxes)[:-10]:
                del self.boxes[k]

    def latest_stamp(self):
        with self.lock:
            return max(self.imgs, default=0)

    def pair_after(self, stamp, timeout=5.0):
        """First synced (image, boxes) pair rendered strictly after `stamp`."""
        end = time.time() + timeout
        while time.time() < end:
            with self.lock:
                common = sorted(k for k in set(self.imgs) & set(self.boxes) if k > stamp)
                if common:
                    k = common[0]
                    return self.imgs[k], self.boxes[k]
            time.sleep(0.02)
        return None

    def set_poses(self, poses):
        # Uses the gz CLI: Node.request() from Python can deadlock with the
        # image subscription callbacks and then hangs forever.
        req = ' '.join(
            f'pose: {{name: "{name}", position: {{x: {x:.3f}, y: {y:.3f}, z: {z:.3f}}}, '
            f'orientation: {{x: {qx:.5f}, y: {qy:.5f}, z: {qz:.5f}, w: {qw:.5f}}}}}'
            for name, (x, y, z), (qx, qy, qz, qw) in poses)
        try:
            out = subprocess.run(
                ['gz', 'service', '-s', '/world/default/set_pose_vector',
                 '--reqtype', 'gz.msgs.Pose_V', '--reptype', 'gz.msgs.Boolean',
                 '--timeout', '2000', '--req', req],
                capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            return False
        return 'data: true' in out.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='finetune/data')
    ap.add_argument('--n', type=int, default=2000)
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--split', default=None, help='force all samples into this split (e.g. test)')
    args = ap.parse_args()
    random.seed(args.seed)

    for split in ('train', 'val', 'test'):
        os.makedirs(f'{args.out}/images/{split}', exist_ok=True)
        os.makedirs(f'{args.out}/labels/{split}', exist_ok=True)

    cap = Capture()
    deadline = time.time() + 15
    while cap.latest_stamp() == 0:
        if time.time() > deadline:
            sys.exit('no frames on /datacam/image - is `gz sim -s -r worlds/datagen.sdf` running '
                     'with the same GZ_IP?')
        time.sleep(0.1)

    counts, t0, i = {}, time.time(), 0
    while i < args.n:
        poses, s, lat = scatter_traffic()
        poses.append(camera_pose(s, lat))
        if not cap.set_poses(poses):
            continue
        # Skip one frame so the render surely reflects the new poses
        first = cap.pair_after(cap.latest_stamp())
        pair = first and cap.pair_after(cap._stamp(first[0].header))
        if pair is None:
            print('timeout waiting for frames, retrying')
            continue
        img, boxes = pair
        frame = np.frombuffer(img.data, np.uint8).reshape(img.height, img.width, 3)
        lines = []
        for b in boxes.annotated_box:
            x0, y0 = b.box.min_corner.x, b.box.min_corner.y
            x1, y1 = b.box.max_corner.x, b.box.max_corner.y
            if b.label < 1 or x1 - x0 < MIN_BOX_PX or y1 - y0 < MIN_BOX_PX:
                continue
            cls = b.label - 1
            counts[cls] = counts.get(cls, 0) + 1
            lines.append(f'{cls} {(x0 + x1) / 2 / img.width:.6f} {(y0 + y1) / 2 / img.height:.6f} '
                         f'{(x1 - x0) / img.width:.6f} {(y1 - y0) / img.height:.6f}')
        split = args.split or ('val' if random.random() < VAL_FRACTION else 'train')
        name = f's{args.seed}_{i:05d}'
        cv2.imwrite(f'{args.out}/images/{split}/{name}.jpg', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR),
                    [cv2.IMWRITE_JPEG_QUALITY, 92])
        with open(f'{args.out}/labels/{split}/{name}.txt', 'w') as f:
            f.write('\n'.join(lines) + ('\n' if lines else ''))
        i += 1
        if i % 50 == 0 or i == args.n:
            rate = i / (time.time() - t0)
            print(f'{i}/{args.n}  {rate:.1f} img/s  boxes per class {dict(sorted(counts.items()))}', flush=True)


if __name__ == '__main__':
    main()
