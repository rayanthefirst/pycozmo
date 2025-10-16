#!/usr/bin/env python
"""
Remote control web interface for Cozmo using pycozmo.

Features:
- Buttons/endpoints for the same actions as examples/rc_cli.py
- Live camera feed over MJPEG at /stream

Usage:
    python examples/rc_web.py --host 0.0.0.0 --port 8080

Then open http://<your-ip>:8080 from another device on the network.

Dependencies:
    pip install fastapi uvicorn[standard]
"""
import sys
from pathlib import Path

if __package__ is None:
    sys.path.append(str(Path(__file__).resolve().parent.parent))


import argparse
import io
import threading
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
import uvicorn

import pycozmo


app = FastAPI(title="Cozmo RC Web")


class RobotController:
    """Manage pycozmo client connection and expose control helpers."""

    def __init__(self, color_camera: bool = True, jpeg_quality: int = 70):
        self.cli: Optional[pycozmo.Client] = None
        self._lock = threading.RLock()
        self._connected = False
        self._head_angle = None
        self._lift_height = None
        self._color_camera = color_camera
        self._jpeg_quality = max(1, min(95, int(jpeg_quality)))

        # Camera state
        self._last_jpeg = None  # bytes
        self._jpeg_lock = threading.Lock()

        # Motion params (match rc_cli defaults)
        self.speed_mmps = 100
        self.head_step_rad = 0.1
        self.lift_step_mm = 5.0

    # --- Camera handling ---
    def _on_camera_image(self, _cli, image):
        # image is a PIL.Image object. Encode to JPEG bytes.
        try:
            bio = io.BytesIO()
            # Lower quality reduces bytes-on-the-wire which helps latency
            image.save(bio, format="JPEG", quality=self._jpeg_quality)
            data = bio.getvalue()
        except Exception:
            return
        with self._jpeg_lock:
            self._last_jpeg = data

    def get_last_jpeg(self) -> Optional[bytes]:
        with self._jpeg_lock:
            return self._last_jpeg

    # --- Connection lifecycle ---
    def connect(self):
        with self._lock:
            if self._connected:
                return
            # Create and connect client
            self.cli = pycozmo.Client()
            self.cli.start()
            self.cli.connect()
            self.cli.wait_for_robot()

            # Raise head a bit to see ahead.
            angle = (
                pycozmo.robot.MAX_HEAD_ANGLE.radians
                - pycozmo.robot.MIN_HEAD_ANGLE.radians
            ) / 2.0
            self.cli.set_head_angle(angle)
            self._head_angle = angle
            self._lift_height = self.cli.lift_position.height.mm

            # Enable camera and register handler
            self.cli.enable_camera(enable=True, color=self._color_camera)
            self.cli.add_handler(
                pycozmo.event.EvtNewRawCameraImage, self._on_camera_image
            )

            self._connected = True

    def disconnect(self):
        with self._lock:
            if not self._connected or not self.cli:
                return
            try:
                self.cli.stop_all_motors()
            except Exception:
                pass
            try:
                self.cli.disconnect()
            except Exception:
                pass
            try:
                self.cli.stop()
            except Exception:
                pass
            self._connected = False
            self.cli = None

    # --- Controls (mirror rc_cli.py) ---
    def drive(self, left_mmps: int, right_mmps: int):
        with self._lock:
            if not self.cli:
                return
            self.cli.drive_wheels(left_mmps, right_mmps)

    def stop(self):
        with self._lock:
            if not self.cli:
                return
            self.cli.stop_all_motors()

    def head_up(self):
        with self._lock:
            if not self.cli:
                return
            new_angle = min(
                (self._head_angle or 0) + self.head_step_rad,
                pycozmo.robot.MAX_HEAD_ANGLE.radians,
            )
            self.cli.set_head_angle(new_angle)
            self._head_angle = new_angle

    def head_down(self):
        with self._lock:
            if not self.cli:
                return
            new_angle = max(
                (self._head_angle or 0) - self.head_step_rad,
                pycozmo.robot.MIN_HEAD_ANGLE.radians,
            )
            self.cli.set_head_angle(new_angle)
            self._head_angle = new_angle

    def lift_up(self):
        with self._lock:
            if not self.cli:
                return
            current = self._lift_height or 0.0
            new_height = min(
                current + self.lift_step_mm, pycozmo.robot.MAX_LIFT_HEIGHT.mm
            )
            self.cli.set_lift_height(new_height)
            self._lift_height = new_height

    def lift_down(self):
        with self._lock:
            if not self.cli:
                return
            current = self._lift_height or 0.0
            new_height = max(
                current - self.lift_step_mm, pycozmo.robot.MIN_LIFT_HEIGHT.mm
            )
            self.cli.set_lift_height(new_height)
            self._lift_height = new_height


controller = RobotController(color_camera=True)


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Cozmo RC</title>
    <style>
      body { font-family: system-ui, sans-serif; margin: 20px; }
      .row { display: flex; gap: 12px; margin: 8px 0; }
      button { padding: 10px 14px; font-size: 16px; }
      #video { max-width: 100%; width: 480px; background: #000; }
      .grid { display: grid; grid-template-columns: repeat(3, 120px); gap: 8px; }
    </style>
  </head>
  <body>
    <h2>Cozmo Remote Control</h2>
    <div class="row">
      <img id="video" src="/stream" alt="Camera stream" />
    </div>
    <div class="row">
      <label>Speed (mm/s): <input id="speed" type="number" value="100" min="0" max="250" step="10"/></label>
      <button onclick="post('/api/stop')">Stop</button>
    </div>
    <div class="grid">
      <div></div>
      <button onclick="drive('forward')">Forward</button>
      <div></div>
      <button onclick="drive('left')">Left</button>
      <div></div>
      <button onclick="drive('right')">Right</button>
      <div></div>
      <button onclick="drive('backward')">Backward</button>
      <div></div>
    </div>
    <div class="row">
      <button onclick="post('/api/head', { dir: 'up' })">Head Up</button>
      <button onclick="post('/api/head', { dir: 'down' })">Head Down</button>
      <button onclick="post('/api/lift', { dir: 'up' })">Lift Up</button>
      <button onclick="post('/api/lift', { dir: 'down' })">Lift Down</button>
    </div>
    <script>
      async function post(path, body) {
        const res = await fetch(path, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: body ? JSON.stringify(body) : null,
        });
        return res.json().catch(() => ({}));
      }
      async function drive(action) {
        const speed = parseInt(document.getElementById('speed').value || '100', 10);
        await post('/api/drive', { action, speed });
      }
      // Stop wheels when leaving page to be safe
      window.addEventListener('beforeunload', () => { navigator.sendBeacon('/api/stop'); });
    </script>
  </body>
</html>
    """


@app.get("/api/status")
def api_status():
    return {
        "connected": True,
        "speed_mmps": controller.speed_mmps,
        "head_step_rad": controller.head_step_rad,
        "lift_step_mm": controller.lift_step_mm,
    }


@app.post("/api/drive")
async def api_drive(request: Request):
    data = {}
    try:
        data = await request.json()
    except Exception:
        data = {}
    action = str(data.get("action") or "").lower()
    try:
        speed = int(data.get("speed") if data.get("speed") is not None else controller.speed_mmps)
    except Exception:
        speed = controller.speed_mmps
    controller.speed_mmps = max(0, min(250, speed))

    if action == "forward":
        controller.drive(controller.speed_mmps, controller.speed_mmps)
    elif action == "backward":
        controller.drive(-controller.speed_mmps, -controller.speed_mmps)
    elif action == "left":
        controller.drive(-controller.speed_mmps, controller.speed_mmps)
    elif action == "right":
        controller.drive(controller.speed_mmps, -controller.speed_mmps)
    else:
        raise HTTPException(status_code=400, detail="invalid action")
    return {"ok": True}


@app.post("/api/head")
async def api_head(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    direction = str(data.get("dir") or "").lower()
    if direction == "up":
        controller.head_up()
    elif direction == "down":
        controller.head_down()
    else:
        raise HTTPException(status_code=400, detail="invalid dir")
    return {"ok": True}


@app.post("/api/lift")
async def api_lift(request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    direction = str(data.get("dir") or "").lower()
    if direction == "up":
        controller.lift_up()
    elif direction == "down":
        controller.lift_down()
    else:
        raise HTTPException(status_code=400, detail="invalid dir")
    return {"ok": True}


@app.api_route("/api/stop", methods=["POST", "GET"])
def api_stop():
    controller.stop()
    return {"ok": True}


@app.get("/stream")
def stream():
    boundary = "frame"

    def gen():
        # Yield latest frames as MJPEG
        last_sent = 0
        while True:
            frame = controller.get_last_jpeg()
            if frame and (len(frame) != last_sent):
                last_sent = len(frame)
                # Send boundary and headers in a small chunk to encourage flush
                yield b"--" + boundary.encode() + b"\r\n"
                yield b"Content-Type: image/jpeg\r\n\r\n"
                # Send payload separately to avoid proxy buffering of large combined chunks
                yield frame
                yield b"\r\n"
            else:
                # Avoid busy loop
                time.sleep(0.03)

    headers = {
        # Strongly discourage any caching or transformation on the path
        "Cache-Control": "no-cache, no-store, must-revalidate, private",
        "Pragma": "no-cache",
        "Expires": "0",
        # Honored by some reverse proxies (e.g., nginx). Harmless elsewhere.
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    }
    return StreamingResponse(
        gen(),
        media_type=f"multipart/x-mixed-replace; boundary={boundary}",
        headers=headers,
    )


# Lifecycle hooks so the app works when started via `uvicorn examples.rc_web:app` as well
@app.on_event("startup")
def _on_startup():
    controller.connect()


@app.on_event("shutdown")
def _on_shutdown():
    controller.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Cozmo RC web server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Port (default: 8080)")
    parser.add_argument("--color", action="store_true", help="Enable color camera")
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=70,
        help="JPEG quality (1-95). Lower = smaller frames (default: 70)",
    )
    args = parser.parse_args()

    controller._color_camera = bool(args.color)
    controller._jpeg_quality = max(1, min(95, int(args.jpeg_quality)))

    # If executed directly, run with uvicorn
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
