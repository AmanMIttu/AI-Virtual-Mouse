# AI Virtual Mouse — Motion Desk

A desktop hand-tracking control room built with **PySide6 / Qt Widgets**, OpenCV, and MediaPipe. Motion Desk opens in preview-only mode; it never moves the pointer or clicks until the user explicitly enables system pointer control.

![Original webcam gesture demonstration](VirtualMouse.gif)

The GIF predates the Qt control room; launch the desktop app with the command below to inspect the new interface.

## Features

- Live webcam preview with MediaPipe hand landmarks and gesture state.
- Camera device index selection and connection/error status.
- Start and stop tracking controls with safe camera and detector cleanup.
- **Preview only by default.** The system pointer toggle starts unchecked; enabling it is an explicit action.
- Cursor sensitivity, smoothing, and pinch-distance controls.
- Index-up/middle-down pointer movement; index/middle pinch click, debounced until release.
- Closing the app requests worker shutdown; the responsive window stays open until the worker exits and cleanup finishes. If a camera backend blocks indefinitely while reading a frame, shutdown remains pending because there is no safe universal way to interrupt that backend call.

## Architecture

- `virtual_mouse_app.py` — responsive Qt control room, camera selection, status, settings, and explicit safety toggle.
- `tracking_worker.py` — background `QThread` for camera capture, MediaPipe processing, rendering, and UI signals. It imports camera dependencies only when tracking starts.
- `HandTracking.py` — MediaPipe landmark detection and drawing helpers; supports the original method names for compatibility.
- `mouse_controller.py` — preview-safe gesture-to-pointer adapter. It has no active backend by default and accepts injected callbacks only when control is enabled.
- `mouse_logic.py` — pure coordinate mapping, smoothing, and gesture predicates.
- `VirtualMouse.py` — legacy OpenCV entry point; preview-only by default and requires `--enable-mouse-control` for real pointer input.

## Requirements and setup

Python **3.11**, a webcam, and a desktop session are required. The repository .venv has been validated with Python 3.11.9. PySide6 provides the native Qt interface; MediaPipe performs hand landmark detection; the OpenCV contrib build supplies the cv2 capture and drawing API required by MediaPipe; PyAutoGUI is used only after pointer control is explicitly enabled. Camera and pointer permissions vary by OS. A headless session cannot use the interactive window.

On Windows PowerShell, use the Python 3.11 launcher entry when available:

```powershell
py -3.11 --version
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install pytest
python virtual_mouse_app.py
```

If `py -3.11` is unavailable, install Python 3.11 and use its full `python.exe` path in place of `py -3.11` when creating `.venv`. Confirm the new environment with `python --version` before installing dependencies.

Choose the camera index and press **Start preview**. The window remains in safe preview mode unless **Enable system pointer** is checked. Press **Stop** or close the window to end tracking.

The legacy preview is also safe by default:

```powershell
python VirtualMouse.py --camera 0
```

Explicitly enable real cursor movement and clicks only when intended:

```powershell
python VirtualMouse.py --camera 0 --enable-mouse-control
```

Run tests without camera or system input:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
python -m pytest -q
```

## Gestures and settings

- **Index up, middle down:** move pointer within the inset camera area.
- **Index and middle fingers pinched:** send one click; release before another click.
- **Sensitivity:** scales cursor travel from the center of the camera region.
- **Smoothing:** higher values reduce jitter but slow the cursor response.
- **Pinch distance:** pixel threshold in the camera frame; tune for camera distance and resolution.

## Limitations and hardware notes

This is a webcam prototype, not a general accessibility device. Detection varies with lighting, hand orientation, occlusion, camera quality, and MediaPipe's handedness assumptions. Pointer control may require OS accessibility permissions and can be unavailable in locked-down, Wayland, or headless environments. Camera indices are system-specific.

### Manual webcam validation

The project owner reports a manual Python 3.11.9 test in which Motion Desk opened the webcam preview, displayed hand landmarks that responded to hand movement, and stopped tracking with the camera released. This release-preparation pass did not repeat the webcam test. The application defaults to preview-only; actual pointer movement and pinch-to-click have not been validated on hardware.

## Tests and attribution

Tests cover coordinate mapping, smoothing, gesture and click debounce, safe preview callbacks, Qt window launch, settings, start/stop transitions, unavailable-camera handling, and side-effect-free module import. Automated tests do not execute mouse or keyboard actions.

The Python 3.11.9 environment passed pip check; imports for PySide6 6.8.3, OpenCV 4.11.0 (opencv-contrib-python), MediaPipe 0.10.21, NumPy 1.26.4, and PyAutoGUI 0.9.54 succeeded. The non-hardware test suite passed 12 tests. Automated tests do not access the webcam or send system mouse/keyboard input.

MIT License; see [LICENSE](LICENSE). Original concept and animated demo by Aman; the original demo is preserved.
