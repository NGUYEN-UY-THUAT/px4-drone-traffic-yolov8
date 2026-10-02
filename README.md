# px4-drone-traffic-yolov8
Giám sát giao thông bằng drone trong môi trường mô phỏng: drone PX4 gắn camera gimbal bay trên một đoạn đường có xe chạy hai chiều trong Gazebo, và model YOLOv8 đã fine-tune trên ảnh mô phỏng nhận diện ô tô, xe buýt, xe tải, xe máy và người lái. Dự án dùng PX4 Autopilot, ROS 2 và Gazebo.

Phát triển từ [monemati/PX4-ROS2-Gazebo-YOLOv8](https://github.com/monemati/PX4-ROS2-Gazebo-YOLOv8).

## Tính năng
- Điều khiển drone bằng bàn phím (WASD + phím mũi tên) qua MAVSDK
- Camera gắn gimbal 2 trục (pitch và yaw), chỉnh được trong khi bay
- Nhận diện vật thể thời gian thực bằng YOLOv8m đã fine-tune trên ảnh mô phỏng, cửa sổ hiển thị thay đổi được kích thước
- Giao thông hai chiều (ô tô, SUV, bán tải, xe buýt và xe máy) trên đoạn đường thẳng của trường đua
- Tất cả dịch vụ chạy trong một cửa sổ tmux chia ô bằng tmuxinator
- Chạy bằng Docker, hỗ trợ GPU và hiển thị qua X11

## Demo
<!-- Video demo sẽ được thêm sau -->

## Model đã fine-tune
YOLOv8m huấn luyện sẵn trên COCO nhận diện xe máy trong mô phỏng rất kém, nên model được fine-tune trên ảnh chụp từ chính môi trường mô phỏng (thư mục `finetune/`). Kết quả trên tập test (300 ảnh):

| Model | mAP50 | mAP50-95 | Recall xe máy |
|-------|-------|----------|---------------|
| `yolov8m.pt` (COCO) | 0.402 | 0.323 | 0.243 |
| `best.pt` đã fine-tune | 0.971 | 0.826 | 0.963 |

File trọng số được đăng ở [bản phát hành v1.0](https://github.com/NGUYEN-UY-THUAT/px4-drone-traffic-yolov8/releases/tag/v1.0), và được `setup_local.sh` cũng như Dockerfile tự động tải về. Để tự tải:
```commandline
mkdir -p finetune/runs/yolov8m_sim/weights
curl -L -o finetune/runs/yolov8m_sim/weights/best.pt https://github.com/NGUYEN-UY-THUAT/px4-drone-traffic-yolov8/releases/download/v1.0/best.pt
```

## Docker
- Build image từ Dockerfile có sẵn. Image dựng sẵn trên Docker Hub là của dự án gốc, không có phần mô phỏng giao thông và model đã fine-tune.

### Chuẩn bị
Cho phép Docker truy cập màn hình X11:
```commandline
xhost +local:docker
```

### Tải image của dự án gốc
```commandline
# Image dựng sẵn của dự án gốc (không có các thay đổi của repo này)
docker pull monemati/px4_ros2_gz_yolov8_image
```

### Build image
```commandline
git clone https://github.com/NGUYEN-UY-THUAT/px4-drone-traffic-yolov8.git PX4-ROS2-Gazebo-YOLOv8
cd PX4-ROS2-Gazebo-YOLOv8
docker build -t px4_ros2_gz_yolov8_image .
```

### Chạy Docker
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

### Những gì chạy trong Docker
Container mở một cửa sổ tmux chia thành 6 ô:

| Ô | Dịch vụ |
|---|---------|
| 1 | Micro XRCE-DDS Agent |
| 2 | PX4 SITL (drone x500_depth) |
| 3 | Cầu nối camera ROS-Gazebo |
| 4 | Hiển thị nhận diện YOLOv8 |
| 5 | Mô phỏng giao thông (`traffic.py`) |
| 6 | Điều khiển drone bằng bàn phím |

Chuyển giữa các ô bằng `Ctrl+b` rồi phím mũi tên.

## Điều khiển bằng bàn phím

Phím được đọc trực tiếp trong terminal, không cần cửa sổ riêng.

### Điều khiển bay
| Phím | Chức năng |
|------|-----------|
| `r` | Arm drone |
| `l` | Hạ cánh |
| `h` | Chế độ Hold: giữ nguyên vị trí và độ cao, bỏ qua bàn phím. Nhấn phím di chuyển bất kỳ để quay lại chế độ Position |
| `p` | Chế độ Position (mặc định sau khi arm): thả hết phím thì drone giữ nguyên vị trí và độ cao |
| `o` | Chế độ Altitude: thả hết phím thì drone giữ độ cao, nhưng có thể trôi ngang |
| `w` / `s` | Tăng / giảm ga |
| `a` / `d` | Xoay trái / phải |
| Phím mũi tên | Roll / Pitch (di chuyển ngang, tiến lùi) |
| `i` | In chế độ bay hiện tại |
| `Ctrl+C` | Thoát |

### Điều khiển camera gimbal
| Phím | Chức năng |
|------|-----------|
| `j` / `k` | Nghiêng camera xuống / lên |
| `n` / `m` | Xoay camera sang trái / phải |

Camera khởi đầu ở góc nghiêng xuống 45 độ. Camera nghiêng được từ 30 độ hướng lên đến nhìn thẳng xuống (90 độ), và xoay tối đa 90 độ sang mỗi bên.

## Hệ thống camera gimbal

Camera của drone được gắn trên gimbal 2 trục pitch và yaw. Script `setup_gimbal.py` sửa file SDF của model drone x500_depth, thay khớp camera cố định bằng:

- **gimbal_yaw_joint**: khớp xoay quanh trục Z (base_link nối với gimbal_link)
- **gimbal_pitch_joint**: khớp xoay quanh trục Y (gimbal_link nối với camera_link)

Mỗi khớp được điều khiển bằng plugin `JointPositionController` ở chế độ lệnh vận tốc (tối đa 1.5 rad/s, không cần chỉnh lực và không tạo phản lực lên drone), nhận lệnh qua các topic Gazebo:
- `/gimbal/cmd_pitch`: góc pitch
- `/gimbal/cmd_yaw`: góc yaw

## Mô phỏng giao thông

`traffic.py` điều khiển 16 phương tiện chạy trên đoạn đường thẳng chính của trường đua Sonoma, cạnh vị trí xuất phát của drone:

| Làn | Hướng | Phương tiện |
|-----|-------|-------------|
| Làn xe máy | đông nam | 4 xe máy |
| Làn ô tô | đông nam | hatchback, SUV, bán tải, xe buýt |
| Làn ô tô | tây bắc | 2 hatchback, SUV, bán tải |
| Làn xe máy | tây bắc | 4 xe máy |

Mỗi xe giữ khoảng cách với xe phía trước trong cùng làn. Khi tới cuối đường, xe quay lại đầu đường với tốc độ hơi khác đi. Vị trí của tất cả các xe được gửi trong một lệnh `/world/default/set_pose_vector` ở mỗi chu kỳ. Script dùng thư viện Python gz-transport nếu import được (ví dụ `python3` của hệ thống với Gazebo Harmonic), nếu không sẽ dùng lệnh `gz service`, chậm hơn.

Các xe đỗ ở khu pit lane trong `worlds/default.sdf` cho tới khi `traffic.py` chạy. Muốn thay đổi giao thông thì sửa bảng `VEHICLES` và `LANES` trong `traffic.py`; mọi tên trong `VEHICLES` phải có trong file world.

Các model xe máy (`models/motorbike_*`) được dựng từ các khối hình học cơ bản, vì Gazebo Fuel không có model xe máy. Tạo lại chúng bằng `python3 models/make_motorbike.py`. Model YOLOv8 COCO gốc thường nhận chúng thành `person` (người lái) thay vì `motorcycle`; đây là lý do model được fine-tune.

## Cài đặt thủ công
### Tạo môi trường ảo
```commandline
# tạo
python -m venv ~/px4-venv

# kích hoạt
source ~/px4-venv/bin/activate
```
### Clone repository
Clone vào `~/PX4-ROS2-Gazebo-YOLOv8`; các lệnh bên dưới dùng đường dẫn này.
```commandline
cd ~
git clone https://github.com/NGUYEN-UY-THUAT/px4-drone-traffic-yolov8.git PX4-ROS2-Gazebo-YOLOv8
```
### Cài PX4
```commandline
cd ~
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
bash ./PX4-Autopilot/Tools/setup/ubuntu.sh
cd PX4-Autopilot/
make px4_sitl
```
### Cài ROS 2
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
### Cài Micro XRCE-DDS Agent & Client
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
### Build ROS 2 workspace
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
### Cài MAVSDK
```commandline
pip install mavsdk
pip install aioconsole
sudo apt install ros-humble-ros-gzgarden
pip install numpy
pip install opencv-python
```
### Cài YOLO
```commandline
pip install ultralytics
```
### Cấu hình thêm
- Thêm các dòng sau vào `~/.bashrc`:
```commandline
source /opt/ros/humble/setup.bash
export GZ_SIM_RESOURCE_PATH=~/.gz/models
```
- Cài các model, world và camera gimbal vào PX4 và Gazebo:
```commandline
cd ~/PX4-ROS2-Gazebo-YOLOv8
./setup_local.sh
```
Script copy `models/` vào `~/.gz/models` và `worlds/default.sdf` vào `~/PX4-Autopilot/Tools/simulation/gz/worlds/`, rồi gắn gimbal vào model x500_depth bằng `setup_gimbal.py` (model gốc được sao lưu thành `model.sdf.bak_nogimbal`). Chạy lại script sau mỗi lần sửa `models/`, `worlds/` hoặc `setup_gimbal.py`. Nếu PX4 không nằm ở `~/PX4-Autopilot`, dùng `PX4_DIR=/duong/dan/toi/PX4-Autopilot ./setup_local.sh`.
- `uav_camera_det.py` dùng trọng số đã fine-tune `finetune/runs/yolov8m_sim/weights/best.pt`, file này không lưu trong git. `setup_local.sh` tự tải nó từ bản phát hành (xem mục Model đã fine-tune ở trên), hoặc bạn có thể tự huấn luyện bằng `python finetune/train.py`.

## Chạy
### Bay bằng bàn phím
Cần mở nhiều terminal.
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
Chọn vào terminal điều khiển bàn phím, nhấn `r` để arm drone. Dùng WASD và phím mũi tên để bay, `j`/`k`/`n`/`m` để điều khiển gimbal, và `l` để hạ cánh.

### Bay bằng ROS 2
Cần mở nhiều terminal.
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

## Ghi nhận
- https://github.com/monemati/PX4-ROS2-Gazebo-YOLOv8 (dự án gốc)
- https://github.com/PX4/PX4-Autopilot
- https://github.com/ultralytics/ultralytics
- https://www.ros.org/
- https://gazebosim.org/
