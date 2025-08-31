Remote Control Web UI (rc_web)

This example exposes a simple web interface to control Cozmo and view the camera stream from another device on your network.

Paths
- Script: `examples/rc_web.py`
- Stream: `GET /stream` (MJPEG)
- UI: `GET /`

Install
- Python 3.8+
- Install deps: `pip install -r requirements.txt`
  - Adds Flask for the web server

Run
- Connect Cozmo’s charger to your computer as usual
- Start the server:
  - `python examples/rc_web.py --host 0.0.0.0 --port 8080`
  - Optional: `--color` enables color camera (if supported)
- From your phone/laptop on the same network, open: `http://<PC_IP>:8080`
  - Tip: find `<PC_IP>` via `ipconfig` (Windows) or `ifconfig` (macOS/Linux)
  - Allow the app through your firewall if prompted

Controls (match rc_cli.py)
- Drive: Forward / Backward / Left / Right
- Head: Up / Down
- Lift: Up / Down
- Stop: Immediately stop motors
- Speed: change mm/s used by drive commands (default 100)

API
- `POST /api/drive {"action":"forward|backward|left|right", "speed":100}`
- `POST /api/head {"dir":"up|down"}`
- `POST /api/lift {"dir":"up|down"}`
- `POST /api/stop`
- `GET /api/status`
- `GET /stream` (multipart/x-mixed-replace MJPEG)

Notes
- The server keeps a persistent pycozmo connection and enables the camera at startup.
- The MJPEG stream is efficient and works in most browsers. If you need WebSocket or HLS, we can extend it.
- If nothing appears, ensure the robot is connected and your firewall allows inbound connections on the chosen port.

