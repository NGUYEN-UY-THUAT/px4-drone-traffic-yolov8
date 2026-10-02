#!/usr/bin/env python3
"""Simulate two-way traffic (cars, bus, motorbikes) on the Sonoma raceway
main straight, right under the drone's spawn point.

Vehicles are static models moved every tick with a single
/world/<world>/set_pose_vector request. Each vehicle keeps a gap to the one
ahead in its lane and re-enters at the start of the road when it reaches the
end, so a steady stream of traffic passes under the camera.
"""

import bisect
import math
import random
import subprocess
import time

WORLD_NAME = "default"
UPDATE_HZ = 20

# Road frame on the main straight: origin, unit vector along the road
# (pointing south-east, downhill) and unit normal (pointing north-east).
ORIGIN = (280.0, -140.0)
ALONG = (0.78348, -0.62142)
NORMAL = (0.62142, 0.78348)
S_MIN, S_MAX = -85.0, 130.0
ROAD_LEN = S_MAX - S_MIN

# Track surface height (m) sampled from the raceway mesh along the straight
HEIGHT_TABLE = [
    (-90, 4.52), (-80, 4.33), (-70, 4.14), (-60, 3.93), (-50, 3.74),
    (-40, 3.54), (-30, 3.34), (-20, 3.14), (-10, 2.94), (0, 2.75),
    (10, 2.54), (20, 2.35), (30, 2.15), (40, 1.95), (50, 1.75),
    (60, 1.55), (70, 1.36), (80, 1.17), (90, 0.97), (100, 0.78),
    (110, 0.60), (120, 0.42), (130, 0.26), (140, 0.11),
]
_HS = [s for s, _ in HEIGHT_TABLE]

# Lanes: lateral offset from the road axis and travel direction (+1 = along).
# The main straight is ~14 m wide (pit wall at -5 m, outer edge at +9 m).
# Traffic keeps right, so motorbikes use the outer lane of each direction.
LANES = {
    'bike_se': (-3.0, +1),
    'car_se': (0.0, +1),
    'car_nw': (3.5, -1),
    'bike_nw': (6.5, -1),
}

# (model name in the world, lane, desired speed m/s, length m)
VEHICLES = [
    ('hatchback_blue_1', 'car_se', 11.0, 4.0),
    ('suv_1', 'car_se', 10.0, 5.0),
    ('pickup_1', 'car_se', 9.0, 5.5),
    ('bus_1', 'car_se', 8.0, 12.5),
    ('hatchback_red_1', 'car_nw', 11.0, 4.0),
    ('suv_2', 'car_nw', 10.0, 5.0),
    ('pickup_2', 'car_nw', 9.5, 5.5),
    ('hatchback_red_2', 'car_nw', 10.5, 4.0),
    ('motorbike_red_1', 'bike_se', 9.0, 1.9),
    ('motorbike_blue_1', 'bike_se', 8.0, 1.9),
    ('motorbike_black_1', 'bike_se', 8.5, 1.9),
    ('motorbike_white_1', 'bike_se', 7.5, 1.9),
    ('motorbike_red_2', 'bike_nw', 8.0, 1.9),
    ('motorbike_blue_2', 'bike_nw', 9.0, 1.9),
    ('motorbike_black_2', 'bike_nw', 7.5, 1.9),
    ('motorbike_white_2', 'bike_nw', 8.5, 1.9),
]

MIN_GAP = 3.0       # bumper-to-bumper distance kept when queued (m)
TIME_HEADWAY = 1.2  # s
BIKE_JITTER = 1.0   # lateral spread of motorbikes inside their lane (m)


def height(s):
    i = min(max(bisect.bisect_right(_HS, s), 1), len(_HS) - 1)
    (s0, z0), (s1, z1) = HEIGHT_TABLE[i - 1], HEIGHT_TABLE[i]
    return z0 + (z1 - z0) * (s - s0) / (s1 - s0)


class Vehicle:
    def __init__(self, name, lane, speed, length, progress):
        self.name = name
        self.lane = lane
        self.base_speed = speed
        self.length = length
        self.progress = progress  # distance travelled along the lane, 0..ROAD_LEN
        self._reroll()
        self.speed = self.desired

    def _reroll(self):
        self.desired = self.base_speed * random.uniform(0.85, 1.15)
        jitter = BIKE_JITTER if self.lane.startswith('bike') else 0.0
        self.lat_offset = random.uniform(-jitter, jitter)

    def advance(self, dt):
        self.progress += self.speed * dt
        if self.progress >= ROAD_LEN:
            self.progress -= ROAD_LEN
            self._reroll()

    def pose(self):
        lat, direction = LANES[self.lane]
        s = S_MIN + self.progress if direction > 0 else S_MAX - self.progress
        lat += self.lat_offset
        x = ORIGIN[0] + s * ALONG[0] + lat * NORMAL[0]
        y = ORIGIN[1] + s * ALONG[1] + lat * NORMAL[1]
        z = height(s)
        yaw = math.atan2(ALONG[1], ALONG[0]) + (0.0 if direction > 0 else math.pi)
        # Nose follows the road grade (positive pitch = nose down)
        grade = (height(s + 1.0) - height(s - 1.0)) / 2.0 * direction
        pitch = -math.atan(grade)
        return x, y, z, pitch, yaw


def update_speeds(vehicles):
    """Keep a safe gap to the vehicle ahead in the same lane."""
    for lane in LANES:
        group = sorted((v for v in vehicles if v.lane == lane), key=lambda v: v.progress)
        for i, v in enumerate(group):
            if len(group) == 1:
                v.speed = v.desired
                continue
            leader = group[(i + 1) % len(group)]
            gap = (leader.progress - v.progress) % ROAD_LEN
            gap -= (leader.length + v.length) / 2
            safe = max(0.0, (gap - MIN_GAP) / TIME_HEADWAY)
            v.speed = min(v.desired, safe)


def quaternion(pitch, yaw):
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return -sp * sy, sp * cy, cp * sy, cp * cy  # x, y, z, w


class PoseSender:
    """Sends all poses in one request; uses gz-transport Python bindings
    when available, otherwise falls back to the `gz service` CLI."""

    def __init__(self):
        self.service = f'/world/{WORLD_NAME}/set_pose_vector'
        try:
            from gz.transport13 import Node
            from gz.msgs10.pose_v_pb2 import Pose_V
            from gz.msgs10.boolean_pb2 import Boolean
            self.node, self.Pose_V, self.Boolean = Node(), Pose_V, Boolean
            print('Using gz-transport Python bindings')
        except ImportError:
            self.node = None
            print('gz-transport Python bindings not found, using gz CLI')

    def send(self, poses):
        if self.node is not None:
            msg = self.Pose_V()
            for name, (x, y, z, qx, qy, qz, qw) in poses:
                p = msg.pose.add()
                p.name = name
                p.position.x, p.position.y, p.position.z = x, y, z
                p.orientation.x, p.orientation.y = qx, qy
                p.orientation.z, p.orientation.w = qz, qw
            self.node.request(self.service, msg, self.Pose_V, self.Boolean, 200)
            return
        req = ' '.join(
            f'pose: {{name: "{name}", position: {{x: {x:.3f}, y: {y:.3f}, z: {z:.3f}}}, '
            f'orientation: {{x: {qx:.5f}, y: {qy:.5f}, z: {qz:.5f}, w: {qw:.5f}}}}}'
            for name, (x, y, z, qx, qy, qz, qw) in poses)
        subprocess.run(
            ['gz', 'service', '-s', self.service,
             '--reqtype', 'gz.msgs.Pose_V', '--reptype', 'gz.msgs.Boolean',
             '--timeout', '1000', '--req', req],
            capture_output=True)


def main():
    # Spread the vehicles of each lane evenly along the road
    vehicles = []
    for lane in LANES:
        names = [v for v in VEHICLES if v[1] == lane]
        for i, (name, _, speed, length) in enumerate(names):
            progress = (i + random.uniform(0.0, 0.5)) * ROAD_LEN / len(names)
            vehicles.append(Vehicle(name, lane, speed, length, progress))

    print(f'Simulating {len(vehicles)} vehicles on a {ROAD_LEN:.0f} m road '
          f'({len(LANES)} lanes). Press Ctrl+C to stop.')
    sender = PoseSender()
    dt = 1.0 / UPDATE_HZ
    last = time.time()
    while True:
        now = time.time()
        step, last = now - last, now
        update_speeds(vehicles)
        for v in vehicles:
            v.advance(step)
        poses = []
        for v in vehicles:
            x, y, z, pitch, yaw = v.pose()
            poses.append((v.name, (x, y, z, *quaternion(pitch, yaw))))
        sender.send(poses)
        time.sleep(max(0.0, dt - (time.time() - now)))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nStopped.')
