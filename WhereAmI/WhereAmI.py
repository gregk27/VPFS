import cv2
import time
import os
# NOTE: pupil_apriltags seems to be broken on Python 3.12, so this needs to be run with <3.12
from pupil_apriltags import Detector

detector = Detector(
    nthreads=4,
    quad_decimate=1,
    quad_sigma=0.1,
    decode_sharpening=1
)

# GStreamer pipeline to work with Jetson
pipeline = ' ! '.join([
    "v4l2src device=/dev/video0",
    "video/x-raw, fomat=YUYV, width=1600, height=896, framerate=15/2",
    "videoconvert",
    "video/x-raw, format=(string)BGR",
    "appsink drop=true sync=false"
    ])

jetson = True

if jetson:
    # Configure camera for best results
    os.system("v4l2-ctl -d /dev/video0 -c focus_auto=0")
    os.system("v4l2-ctl -d /dev/video0 -c focus_absolute=0")
    # Readback current settings
    os.system("v4l2-ctl -d /dev/video0 -C focus_auto")
    os.system("v4l2-ctl -d /dev/video0 -C focus_absolute")
    cam = cv2.VideoCapture(pipeline, cv2.CAP_GSTREAMER)
else:
    cam = cv2.VideoCapture(0) # this is the magic!

    cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1600)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 900)

frameWidth = int(cam.get(cv2.CAP_PROP_FRAME_WIDTH))
frameHeight = int(cam.get(cv2.CAP_PROP_FRAME_HEIGHT))
print(frameWidth, 'x', frameHeight)

font = cv2.FONT_HERSHEY_PLAIN
def show_tags(img, detections):
    for tag in detections:
        img = cv2.putText(img, str(tag.tag_id), (int(tag.center[0]), int(tag.center[1])), font, 3, (0, 0, 255), 2, cv2.LINE_AA)
        img = cv2.rectangle(img, (int(tag.corners[0][0]), int(tag.corners[0][1])), (int(tag.corners[2][0]), int(tag.corners[2][1])), (0, 0, 255), 2)
    return img

refTags = {
        0: (0,0,0),
        }
def computeCameraPos(detections):
    camPos = (999, 999, 999)
    for det in detections:
        if det.tag_id in refTags:
            refPos = refTags[det.tag_id]
            tagPos = (det.pose_t[0][0], det.pose_t[1][0], det.pose_t[2][0])
            camPos = (refPos[0]-tagPos[0], refPos[1]-tagPos[1], refPos[2]-tagPos[2])
    return camPos

if not cam.isOpened():
    print("Cannot open camera")
    exit()

lastTime = time.time()
while True:
    # Capture the frame
    ret, frame = cam.read()

    if not ret:
        print("Failed to receive frame, exiting")
        break

    # Sharpen the image
    # strength = 1.75
    # blurred = cv2.GaussianBlur(frame, (0, 0), 1)
    # frame = cv2.addWeighted(frame, 1.0 + strength, blurred, -strength, 0)

    # Process the frame
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Detect tags
    detections = detector.detect(gray, True, (950, 950, 800, 455), 0.1)
    frame = show_tags(frame, detections)
    cameraPos = computeCameraPos(detections)

    # Compute FPS
    frameTime = time.time() - lastTime
    fps = 1/frameTime
    lastTime = time.time()

    # Add info block
    cv2.putText(frame, f"{frameWidth}x{frameHeight} @ {fps:.2f} fps", (0,frameHeight - 10), font, 3, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(frame, f"X{cameraPos[0]:.2f} Y{cameraPos[1]:.2f} Z{cameraPos[2]:.2f}", (0, frameHeight-200), font, 3, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.imshow('frame', frame)

    cv2.waitKey(1)

cam.release()
cv2.destroyAllWindows()
