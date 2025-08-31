#!/usr/bin/env python
"""Simple command line RC controller for Cozmo.

This example combines driving, camera streaming and text-to-speech.
It requires ``opencv-python``, ``gTTS`` and ``pydub`` for the TTS feature.

Controls:
    w - forward
    s - backward
    a - turn left
    d - turn right
    space - stop motors
    ESC - exit

Type text in the terminal and press Enter for the robot to speak it.
"""

import threading
import tempfile
import os

import cv2
import numpy as np
from gtts import gTTS
from pydub import AudioSegment

import pycozmo

# Last camera frame.
last_frame = None


def on_camera_image(cli, image):
    """Convert PIL image to OpenCV image."""
    global last_frame
    last_frame = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def say_text(cli, text: str) -> None:
    """Generate speech for ``text`` and play it on the robot."""
    tts = gTTS(text=text, lang="en")
    tmp_mp3 = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
    tts.save(tmp_mp3.name)
    sound = AudioSegment.from_mp3(tmp_mp3.name)
    tmp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    sound.set_frame_rate(22050).set_channels(1).export(
        tmp_wav.name, format="wav")
    cli.play_audio(tmp_wav.name)
    cli.wait_for(pycozmo.event.EvtAudioCompleted)
    os.unlink(tmp_mp3.name)
    os.unlink(tmp_wav.name)


def input_loop(cli):
    """Read text from the user and speak it."""
    while True:
        try:
            text = input("Say> ")
        except EOFError:
            break
        if text:
            try:
                say_text(cli, text)
            except Exception as exc:
                print("Failed to speak:", exc)


def main():
    with pycozmo.connect(enable_procedural_face=False) as cli:
        # Raise head a bit to see ahead.
        angle = (pycozmo.robot.MAX_HEAD_ANGLE.radians -
                 pycozmo.robot.MIN_HEAD_ANGLE.radians) / 2.0
        cli.set_head_angle(angle)

        # Enable camera and register handler.
        cli.enable_camera(enable=True, color=True)
        cli.add_handler(pycozmo.event.EvtNewRawCameraImage, on_camera_image)

        # Start text input thread.
        threading.Thread(target=input_loop, args=(cli,), daemon=True).start()

        speed = 100  # mm/s
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
            elif key == ord(' '):
                cli.stop_all_motors()

        cli.stop_all_motors()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
