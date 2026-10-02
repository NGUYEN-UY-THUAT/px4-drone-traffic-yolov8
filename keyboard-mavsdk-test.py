import asyncio
import subprocess
import sys
from mavsdk import System
import KeyPressModule as kp

kp.init()
drone = System()

roll, pitch, throttle, yaw = 0, 0, 0.5, 0
is_connected = False

# Flight mode requested from the keyboard: "position", "altitude" or "hold"
control_mode = None
MOVE_KEYS = ["LEFT", "RIGHT", "UP", "DOWN", "w", "s", "a", "d"]

# Gimbal state
# Positive pitch tilts the camera down; must match the joint limits in setup_gimbal.py
gimbal_pitch = 0.7854  # initial 45 deg down
gimbal_yaw = 0.0
GIMBAL_STEP = 0.05  # rad per tick (~2.9 deg, ~29 deg/s while held)
GIMBAL_PITCH_MIN = -0.5   # 30 deg up
GIMBAL_PITCH_MAX = 1.57   # straight down
# Positive yaw turns the camera left
GIMBAL_YAW_MIN = -1.57
GIMBAL_YAW_MAX = 1.57


def log(msg):
    sys.stdout.write(f"{msg}\r\n")
    sys.stdout.flush()


_gimbal_procs = {}
_gimbal_pending = {}

def set_gimbal(topic, value):
    _gimbal_pending[topic] = value
    flush_gimbal()


def flush_gimbal():
    # Send the latest target for each topic, one `gz topic` process at a time.
    # A target that arrives while a process is still running is kept and sent
    # on a later tick, so the final position after a key release is never lost.
    for topic, value in list(_gimbal_pending.items()):
        prev = _gimbal_procs.get(topic)
        if prev is not None and prev.poll() is None:
            continue
        del _gimbal_pending[topic]
        _gimbal_procs[topic] = subprocess.Popen(
            ['gz', 'topic', '-t', topic, '-m', 'gz.msgs.Double',
             '-p', f'data: {value:.4f}'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )


async def set_control_mode(my_drone, mode):
    """Switch PX4 flight mode. Centered sticks hold altitude (altitude mode)
    or position + altitude (position mode); hold mode locks position and
    altitude and ignores the sticks."""
    global control_mode
    if mode == control_mode:
        return
    try:
        if mode == "position":
            await my_drone.manual_control.start_position_control()
            log("-- Position mode: release keys to hold position + altitude")
        elif mode == "altitude":
            await my_drone.manual_control.start_altitude_control()
            log("-- Altitude mode: release keys to hold altitude (may drift)")
        elif mode == "hold":
            await my_drone.action.hold()
            log("-- Hold mode: position + altitude locked (move keys to resume)")
        control_mode = mode
    except Exception as e:
        log(f"-- Switch to {mode} mode failed: {e}")


async def getKeyboardInput(my_drone):
    global roll, pitch, throttle, yaw, gimbal_pitch, gimbal_yaw, control_mode
    while True:
        roll, pitch, throttle, yaw = 0, 0, 0.5, 0
        value = 0.5

        # Any movement key while holding hands control back to the keyboard
        if control_mode == "hold" and any(kp.getKey(k) for k in MOVE_KEYS):
            await set_control_mode(my_drone, "position")

        # Flight controls
        if kp.getKey("LEFT"):
            pitch = -value
        elif kp.getKey("RIGHT"):
            pitch = value
        if kp.getKey("UP"):
            roll = value
        elif kp.getKey("DOWN"):
            roll = -value
        if kp.getKey("w"):
            throttle = 1
        elif kp.getKey("s"):
            throttle = 0
        if kp.getKey("a"):
            yaw = -value
        elif kp.getKey("d"):
            yaw = value
        elif kp.getKey("i"):
            asyncio.ensure_future(print_flight_mode(my_drone))
        elif kp.getKey("r"):
            try:
                await my_drone.action.arm()
                log("-- Armed!")
            except Exception as e:
                log(f"-- Arm failed: {e}")
            else:
                # Leave HOLD so PX4 accepts the keyboard stick inputs
                control_mode = None
                await set_control_mode(my_drone, "position")
        elif kp.getKey("l"):
            try:
                await my_drone.action.land()
                log("-- Landing!")
                control_mode = None
            except Exception as e:
                log(f"-- Land failed: {e}")
        elif kp.getKey("h"):
            await set_control_mode(my_drone, "hold")
        elif kp.getKey("p"):
            await set_control_mode(my_drone, "position")
        elif kp.getKey("o"):
            await set_control_mode(my_drone, "altitude")

        # Gimbal controls
        if kp.getKey("j"):
            gimbal_pitch = min(GIMBAL_PITCH_MAX, gimbal_pitch + GIMBAL_STEP)
            set_gimbal('/gimbal/cmd_pitch', gimbal_pitch)
        elif kp.getKey("k"):
            gimbal_pitch = max(GIMBAL_PITCH_MIN, gimbal_pitch - GIMBAL_STEP)
            set_gimbal('/gimbal/cmd_pitch', gimbal_pitch)
        if kp.getKey("n"):
            gimbal_yaw = min(GIMBAL_YAW_MAX, gimbal_yaw + GIMBAL_STEP)
            set_gimbal('/gimbal/cmd_yaw', gimbal_yaw)
        elif kp.getKey("m"):
            gimbal_yaw = max(GIMBAL_YAW_MIN, gimbal_yaw - GIMBAL_STEP)
            set_gimbal('/gimbal/cmd_yaw', gimbal_yaw)
        flush_gimbal()

        await asyncio.sleep(0.1)


async def print_flight_mode(my_drone):
    async for flight_mode in my_drone.telemetry.flight_mode():
        log(f"FlightMode: {flight_mode}")


async def manual_control_drone(my_drone):
    global roll, pitch, throttle, yaw
    while True:
        await my_drone.manual_control.set_manual_control_input(roll, pitch, throttle, yaw)
        await asyncio.sleep(0.1)


async def run_drone():
    global is_connected
    asyncio.ensure_future(getKeyboardInput(drone))
    await drone.connect(system_address="udp://:14540")
    log("Waiting for drone to connect...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            log("-- Connected to drone!")
            break
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            log("-- Global position state is good enough for flying.")
            break
    is_connected = True
    log("-- Ready! Press 'r' to arm the drone.")
    asyncio.ensure_future(manual_control_drone(drone))


async def run():
    global roll, pitch, throttle, yaw
    """Main function to connect to the drone and input manual controls"""
    await asyncio.gather(run_drone())


if __name__ == "__main__":
    asyncio.ensure_future(run())
    asyncio.get_event_loop().run_forever()
