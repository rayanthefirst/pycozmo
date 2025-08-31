#!/usr/bin/env python
"""Simple command line RC controller for Cozmo.

This example combines driving and camera streaming.

Controls:
    w - forward
    s - backward
    a - turn left
    d - turn right
    r - raise head
    f - lower head
    t - raise lift
    g - lower lift
    space - stop motors
    ESC - exit
"""

import cv2
import numpy as np

import pycozmo

# Last camera frame.
last_frame = None


def on_camera_image(cli, image):
    """Convert PIL image to OpenCV image."""
    global last_frame
    last_frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def main():
    with pycozmo.connect(enable_procedural_face=False) as cli:
        # Raise head a bit to see ahead.
        angle = (pycozmo.robot.MAX_HEAD_ANGLE.radians -
                 pycozmo.robot.MIN_HEAD_ANGLE.radians) / 2.0
        cli.set_head_angle(angle)
        head_angle = angle
        lift_height = cli.lift_position.height.mm

        # Enable camera and register handler.
        cli.enable_camera(enable=True, color=True)
        cli.add_handler(pycozmo.event.EvtNewRawCameraImage, on_camera_image)

        speed = 100  # mm/s
        head_step = 0.1  # radians
        lift_step = 5.0  # mm
        while True:
            if last_frame is not None:
                cv2.imshow("Cozmo", last_frame)
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            elif key == ord('w'):
                cli.drive_wheels(speed, speed)
            elif key == ord('s'):
                cli.drive_wheels(-speed, -speed)
            elif key == ord('a'):
                cli.drive_wheels(-speed, speed)
            elif key == ord('d'):
                cli.drive_wheels(speed, -speed)
            elif key == ord('r'):
                head_angle = min(head_angle + head_step,
                                 pycozmo.robot.MAX_HEAD_ANGLE.radians)
                cli.set_head_angle(head_angle)
            elif key == ord('f'):
                head_angle = max(head_angle - head_step,
                                 pycozmo.robot.MIN_HEAD_ANGLE.radians)
                cli.set_head_angle(head_angle)
            elif key == ord('t'):
                lift_height = min(lift_height + lift_step,
                                  pycozmo.robot.MAX_LIFT_HEIGHT.mm)
                cli.set_lift_height(lift_height)
            elif key == ord('g'):
                lift_height = max(lift_height - lift_step,
                                  pycozmo.robot.MIN_LIFT_HEIGHT.mm)
                cli.set_lift_height(lift_height)
            elif key == ord(' '):
                cli.stop_all_motors()

        cli.stop_all_motors()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
