# PX4-ROS2-Gazebo-YOLOv8
Aerial Object Detection using a Drone with PX4 Autopilot and ROS 2. PX4 SITL and Gazebo Garden used for Simulation. YOLOv8 used for Object Detection.

## Features
- Keyboard-controlled drone flight (WASD + arrow keys) via MAVSDK
- 2-axis gimbal camera control (pitch and yaw) adjustable during flight
- YOLOv8 real-time object detection with resizable display window
- Two-way traffic (cars, SUVs, pickups, a bus and motorbikes) on the raceway straight for traffic-monitoring demos
- All services orchestrated via tmuxinator in a single tiled-pane window
- Docker-based setup with GPU passthrough and X11 forwarding

## Demo
https://github.com/monemati/PX4-ROS2-Gazebo-YOLOv8/assets/58460889/fab19f49-0be6-43ea-a4e4-8e9bc8d59af9

## Docker
- You can pull the image (already built) or use the provided Dockerfile.

### Prerequisites
Allow Docker to access the X11 display:
```commandline
xhost +local:docker
```

### Pull The Image
```commandline
# Already built and uploaded in dockerhub; You can skip this step, if you want to build your own custom image.
docker pull monemati/px4_ros2_gz_yolov8_image
```

### Build Custom Image
```commandline
git clone https://github.com/monemati/PX4-ROS2-Gazebo-YOLOv8.git
cd PX4-ROS2-Gazebo-YOLOv8
docker build -t px4_ros2_gz_yolov8_image .
```

### Run The Docker
```commandline
XAUTH=/tmp/.docker.xauth
touch $XAUTH
xauth nlist $DISPLAY | sed -e 's/^..../ffff/' | xauth -f $XAUTH nmerge -
docker run --privileged -it --gpus all \
  -e NVIDIA_DRIVER_CAPABILITIES=all \
  -e NVIDIA_VISIBLE_DEVICES=all \
  -e MESA_GL_VERSION_OVERRIDE=3.3 \
  --volume="/tmp/.X11-unix:/tmp/.X11-unix:rw" \
  --env="XAUTHORITY=$XAUTH" \
  --volume="$XAUTH:$XAUTH" \
  --network=host --ipc=host --shm-size=2gb \
  --env="DISPLAY=$DISPLAY" \
  --env="QT_X11_NO_MITSHM=1" \
  --rm --name px4_ros2_gz_yolov8_container \
  px4_ros2_gz_yolov8_image
```

### What Launches in Docker
The container starts a single tmux window with 6 tiled panes:

| Pane | Service |
|------|---------|
| 1 | Micro XRCE-DDS Agent |
| 2 | PX4 SITL (x500_depth drone) |
| 3 | ROS-Gazebo camera bridge |
| 4 | YOLOv8 detection display |
| 5 | Traffic simulation (`traffic.py`) |
| 6 | Keyboard drone controller |

Switch between panes with `Ctrl+b` then arrow keys.

## Keyboard Controls

All keyboard input is handled directly in the terminal (no separate window needed).

### Flight Controls
| Key | Action |
|-----|--------|
| `r` | Arm the drone |
| `l` | Land |
| `h` | Hold mode: lock position and altitude, ignore the keyboard. Any movement key switches back to position mode |
| `p` | Position mode (default after arming): release all keys to hold position and altitude |
| `o` | Altitude mode: release all keys to hold altitude; the drone may drift horizontally |
| `w` / `s` | Throttle up / down |
| `a` / `d` | Yaw left / right |
| Arrow keys | Roll / Pitch |
| `i` | Print flight mode |
| `Ctrl+C` | Quit |

### Gimbal Camera Controls
| Key | Action |
|-----|--------|
| `j` / `k` | Gimbal pitch down / up |
| `n` / `m` | Gimbal yaw left / right |

The camera starts at 45 degrees downward. It can tilt from 30 degrees up to straight down (90 degrees), and turn up to 90 degrees left or right.

## Gimbal Camera System

The drone's camera is mounted on a 2-axis gimbal with pitch and yaw control. During Docker build, `setup_gimbal.py` modifies the x500_depth drone model SDF to replace the fixed camera joint with:

- **gimbal_yaw_joint**: Revolute joint around the Z axis (base_link to gimbal_link)
- **gimbal_pitch_joint**: Revolute joint around the Y axis (gimbal_link to camera_link)

Each joint is controlled by a `JointPositionController` plugin with velocity commands (up to 1.5 rad/s, no torque tuning and no reaction torques on the drone), responding to Gazebo transport topics:
- `/gimbal/cmd_pitch` — pitch angle command
- `/gimbal/cmd_yaw` — yaw angle command

## Traffic Simulation

`traffic.py` drives 16 vehicles along the main straight of the Sonoma raceway, next to the drone's spawn point:

| Lane | Direction | Vehicles |
|------|-----------|----------|
| Motorbike lane | south-east | 4 motorbikes |
| Car lane | south-east | hatchback, SUV, pickup, bus |
| Car lane | north-west | 2 hatchbacks, SUV, pickup |
| Motorbike lane | north-west | 4 motorbikes |

Each vehicle keeps a gap to the one ahead in its lane, and when it reaches the end of the road it re-enters at the start with a slightly different speed. All poses are sent in a single `/world/default/set_pose_vector` request per tick. The script uses the gz-transport Python bindings when they are importable (e.g. system `python3` with Gazebo Harmonic), and falls back to the slower `gz service` CLI otherwise.

The vehicles are parked in the pit lane in `worlds/default.sdf` until `traffic.py` starts. To change the traffic, edit the `VEHICLES` and `LANES` tables in `traffic.py`; every name in `VEHICLES` must be included in the world file.

The motorbike models (`models/motorbike_*`) are built from primitive shapes, because Gazebo Fuel has no motorcycle model. Regenerate them with `python3 models/make_motorbike.py`. The pretrained COCO YOLOv8 model often detects them as `person` (the rider) rather than `motorcycle`.

## Manual Installation
### Create a virtual environment
```commandline
# create
python -m venv ~/px4-venv

# activate
source ~/px4-venv/bin/activate
```
### Clone repository
```commandline
git clone https://github.com/monemati/PX4-ROS2-Gazebo-YOLOv8.git
```
### Install PX4
```commandline
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
bash ./PX4-Autopilot/Tools/setup/ubuntu.sh
cd PX4-Autopilot/
make px4_sitl
```
### Install ROS 2
```commandline
cd ~
sudo apt update && sudo apt install locales
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
sudo apt install software-properties-common
sudo add-apt-repository universe
sudo apt update && sudo apt install curl -y
sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null
sudo apt update && sudo apt upgrade -y
sudo apt install ros-humble-desktop
sudo apt install ros-dev-tools
source /opt/ros/humble/setup.bash && echo "source /opt/ros/humble/setup.bash" >> .bashrc
pip install --user -U empy pyros-genmsg setuptools
```
### Setup Micro XRCE-DDS Agent & Client
```commandline
cd ~
git clone https://github.com/eProsima/Micro-XRCE-DDS-Agent.git
cd Micro-XRCE-DDS-Agent
mkdir build
cd build
cmake ..
make
sudo make install
sudo ldconfig /usr/local/lib/
```
### Build ROS 2 Workspace
```commandline
mkdir -p ~/ws_sensor_combined/src/
cd ~/ws_sensor_combined/src/
git clone https://github.com/PX4/px4_msgs.git
git clone https://github.com/PX4/px4_ros_com.git
cd ..
source /opt/ros/humble/setup.bash
colcon build

mkdir -p ~/ws_offboard_control/src/
cd ~/ws_offboard_control/src/
git clone https://github.com/PX4/px4_msgs.git
git clone https://github.com/PX4/px4_ros_com.git
cd ..
source /opt/ros/humble/setup.bash
colcon build
```
### Install MAVSDK
```commandline
pip install mavsdk
pip install aioconsole
sudo apt install ros-humble-ros-gzgarden
pip install numpy
pip install opencv-python
```
### Install YOLO
```commandline
pip install ultralytics
```
### Additional Configs
- Put below lines in your bashrc:
```commandline
source /opt/ros/humble/setup.bash
export GZ_SIM_RESOURCE_PATH=~/.gz/models
```
- Install the models, the world and the gimbal camera into PX4 and Gazebo:
```commandline
cd ~/PX4-ROS2-Gazebo-YOLOv8
./setup_local.sh
```
The script copies `models/` to `~/.gz/models` and `worlds/default.sdf` to `~/PX4-Autopilot/Tools/simulation/gz/worlds/`, then adds the gimbal to the x500_depth model with `setup_gimbal.py` (the original model is backed up as `model.sdf.bak_nogimbal`). Run it again after changing `models/`, `worlds/` or `setup_gimbal.py`. If PX4 is not in `~/PX4-Autopilot`, use `PX4_DIR=/path/to/PX4-Autopilot ./setup_local.sh`.
- `uav_camera_det.py` uses the fine-tuned weights `finetune/runs/yolov8m_sim/weights/best.pt`, which are not stored in git. Download them into that path, or train them with `python finetune/train.py`.

## Run
### Fly using Keyboard
You need several terminals.
```commandline
Terminal #1:
cd ~/Micro-XRCE-DDS-Agent
MicroXRCEAgent udp4 -p 8888

Terminal #2:
cd ~/PX4-Autopilot
PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE="273.61,-143.23,3.58,0.00,0,-0.7" PX4_GZ_MODEL=x500_depth ./build/px4_sitl_default/bin/px4

Terminal #3:
ros2 run ros_gz_bridge parameter_bridge /world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/image@sensor_msgs/msg/Image[gz.msgs.Image --ros-args -r /world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/image:=/camera

Terminal #4:
source ~/px4-venv/bin/activate
cd ~/PX4-ROS2-Gazebo-YOLOv8
python uav_camera_det.py

Terminal #5:
cd ~/PX4-ROS2-Gazebo-YOLOv8
python3 traffic.py

Terminal #6:
source ~/px4-venv/bin/activate
cd ~/PX4-ROS2-Gazebo-YOLOv8
python keyboard-mavsdk-test.py
```
Focus on the keyboard controller terminal, then press `r` to arm the drone. Use WASD and arrow keys for flight, `j`/`k`/`n`/`m` for gimbal control, and `l` for landing.

### Fly using ROS 2
You need several terminals.
```commandline
Terminal #1:
cd ~/Micro-XRCE-DDS-Agent
MicroXRCEAgent udp4 -p 8888

Terminal #2:
cd ~/PX4-Autopilot
PX4_SYS_AUTOSTART=4002 PX4_GZ_MODEL_POSE="273.61,-143.23,3.58,0.00,0,-0.7" PX4_GZ_MODEL=x500_depth ./build/px4_sitl_default/bin/px4

Terminal #3:
ros2 run ros_gz_bridge parameter_bridge /world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/image@sensor_msgs/msg/Image[gz.msgs.Image --ros-args -r /world/default/model/x500_depth_0/link/camera_link/sensor/IMX214/image:=/camera

Terminal #4:
source ~/px4-venv/bin/activate
cd ~/PX4-ROS2-Gazebo-YOLOv8
python uav_camera_det.py

Terminal #5:
cd ~/ws_offboard_control
source /opt/ros/humble/setup.bash
source install/local_setup.bash
ros2 run px4_ros_com offboard_control
```

## Acknowledgement
- https://github.com/PX4/PX4-Autopilot
- https://github.com/ultralytics/ultralytics
- https://www.ros.org/
- https://gazebosim.org/
