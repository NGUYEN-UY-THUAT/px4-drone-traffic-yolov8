# Basic ROS 2 program to subscribe to real-time streaming 
# video from your built-in webcam
# Author:
# - Addison Sears-Collins
# - https://automaticaddison.com
  
# Import the necessary libraries
import rclpy # Python library for ROS 2
from rclpy.node import Node # Handles the creation of nodes
from sensor_msgs.msg import Image # Image is the message type
import numpy as np
import cv2 # OpenCV library
from ultralytics import YOLO # YOLO library

# Load the YOLOv8 model
model = YOLO('finetune/runs/yolov8m_sim/weights/best.pt')


class ImageSubscriber(Node):
  """
  Create an ImageSubscriber class, which is a subclass of the Node class.
  """
  def __init__(self):
    """
    Class constructor to set up the node
    """
    # Initiate the Node class's constructor and give it a name
    super().__init__('image_subscriber')
      
    # Create the subscriber. This subscriber will receive an Image
    # from the video_frames topic. The queue size is 10 messages.
    self.subscription = self.create_subscription(
      Image, 
      'camera', 
      self.listener_callback, 
      10)
    self.subscription # prevent unused variable warning
      
    # Create a resizable window
    cv2.namedWindow('Detected Frame', cv2.WINDOW_NORMAL)
   
  def listener_callback(self, data):
    """
    Callback function.
    """
    # Display the message on the console
    self.get_logger().info('Receiving video frame')
 
    # Convert ROS Image message to OpenCV image
    # (done with numpy instead of cv_bridge, which breaks under numpy 2.x)
    current_frame = np.frombuffer(data.data, dtype=np.uint8).reshape(data.height, data.step)
    current_frame = current_frame[:, :data.width * 3].reshape(data.height, data.width, 3)
    if data.encoding == 'rgb8':
      current_frame = cv2.cvtColor(current_frame, cv2.COLOR_RGB2BGR)
    image = current_frame
    # Object Detection
    # COCO: 0 person, 2 car, 3 motorcycle, 5 bus, 7 truck
    results = model.predict(image, classes=[0, 2, 3, 5, 7])
    img = results[0].plot()
    # Show Results
    cv2.imshow('Detected Frame', img)    
    cv2.waitKey(1)
  
def main(args=None):
  
  # Initialize the rclpy library
  rclpy.init(args=args)
  
  # Create the node
  image_subscriber = ImageSubscriber()
  
  # Spin the node so the callback function is called.
  rclpy.spin(image_subscriber)
  
  # Destroy the node explicitly
  # (optional - otherwise it will be done automatically
  # when the garbage collector destroys the node object)
  image_subscriber.destroy_node()
  
  # Shutdown the ROS client library for Python
  rclpy.shutdown()
  
if __name__ == '__main__':
  main()
