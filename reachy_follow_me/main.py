"""Installable Reachy Mini Control App. Fixed webcam → bounded SDK commands.

Loopback only; no LAN discovery, image upload, automatic torque enable or calibration.
On Wireless, use an explicit SSH local port forward to keep the webcam in a secure
localhost browser context. A moving robot camera is not a fixed teleoperator camera.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import threading
import time

import httpx
import numpy as np
from fastapi import Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from platformdirs import user_cache_path
from reachy_mini import ReachyMiniApp
from reachy_mini.utils.rotation import Rotation

from .adapter import checked_target, sdk_antennas, classroom_antennas

PACKAGE = Path(__file__).resolve().parent
ORIGINS = {"http://127.0.0.1:8043", "http://localhost:8043"}

class ReachyFollowMe(ReachyMiniApp):
    custom_app_url = "http://127.0.0.1:8043"
    request_media_backend = "no_media"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Do not scout the LAN if the Control daemon is absent.
        self.daemon_on_localhost = True
        self.lock = threading.RLock()
        self.ready = False
        self.armed = False
        self.has_control = False
        self.hold_requested = False
        self.enable_requested = False
        self.epoch = 0
        self.last_target = 0.
        self.desired = None
        self.actual = {"yaw": 0., "left": 0., "right": 0.}
        self.message = "等待本機 Reachy Mini daemon"
        self.asset_message = "尚未下載辨識模型"
        self.downloading = False
        self.cache = Path(os.environ.get("REACHY_FOLLOW_ME_CACHE", user_cache_path("reachy-follow-me")))
        self.web = self.cache / "web"
        self.web.mkdir(parents=True, exist_ok=True)
        shutil.copytree(PACKAGE / "web", self.web, dirs_exist_ok=True)
        self.manifest = json.loads((PACKAGE / "assets-manifest.json").read_text())
        self.assets_ready = all((self.cache / a["path"]).is_file() and hashlib.sha256((self.cache / a["path"]).read_bytes()).hexdigest() == a["sha256"] for a in self.manifest)
        if self.assets_ready:
            self.asset_message = "辨識模型已驗證，可離線使用"
        app = self.settings_app

        @app.middleware("http")
        async def guard(request: Request, call_next):
            if request.headers.get("host") not in {"127.0.0.1:8043", "localhost:8043"}:
                return JSONResponse({"error": "Loopback host required"}, status_code=403)
            if request.method not in {"GET", "HEAD"}:
                if request.headers.get("origin") not in ORIGINS or request.headers.get("content-type") != "application/json":
                    return JSONResponse({"error": "Same-origin JSON required"}, status_code=403)
                if len(await request.body()) > 2048:
                    return JSONResponse({"error": "Request too large"}, status_code=413)
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response

        @app.get("/")
        async def index():
            return FileResponse(self.web / "index.html")

        @app.get("/api/status")
        async def status():
            with self.lock:
                return {"mujoco": False, "hardware": True, "ready": self.ready, "armed": self.armed,
                        "angles": self.actual, "message": self.message,
                        "assets_ready": self.assets_ready, "asset_message": self.asset_message}

        @app.post("/api/enable")
        async def enable(request: Request):
            body = await request.json()
            if body != {"confirmed": True} or not self.ready:
                raise HTTPException(409, "Reachy not ready or confirmation missing")
            with self.lock:
                self.enable_requested = True
                self.epoch += 1
            return {"ok": True}

        @app.post("/api/stop")
        async def stop():
            self.disarm("已停止；再次啟用才能追蹤")
            return {"ok": True}

        @app.post("/api/target")
        async def target(request: Request):
            try:
                body = await request.json()
                angles = checked_target(body)
            except (ValueError, TypeError, AttributeError):
                raise HTTPException(400, "Invalid bounded target")
            with self.lock:
                if not body["active"]:
                    self.disarm("輸入停止；保持姿勢")
                elif self.armed:
                    self.desired = angles
                    self.last_target = time.monotonic()
                else:
                    raise HTTPException(409, "Enable the app before controlling Reachy")
            return {"ok": True}

        @app.post("/api/assets")
        async def assets():
            with self.lock:
                if not self.downloading and not self.assets_ready:
                    self.downloading = True
                    threading.Thread(target=self.download_assets, daemon=True).start()
            return {"ok": True}

        app.mount("/static", StaticFiles(directory=self.web), name="follow-me-static")

    def disarm(self, message):
        with self.lock:
            # Repeated inactive browser packets must not re-sample a sagging
            # measured pose: capture the hold target only on the transition.
            if self.armed or self.enable_requested:
                self.hold_requested = self.has_control
            self.armed = False
            self.enable_requested = False
            self.desired = None
            self.epoch += 1
            self.message = message

    def download_assets(self):
        try:
            with httpx.Client(follow_redirects=True, timeout=180) as client:
                for asset in self.manifest:
                    path = (self.cache / asset["path"]).resolve()
                    if not path.is_relative_to(self.web.resolve()) or not asset["url"].startswith("https://"):
                        raise ValueError("Invalid packaged manifest")
                    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == asset["sha256"]:
                        continue
                    self.asset_message = "下載：" + path.name
                    response = client.get(asset["url"])
                    response.raise_for_status()
                    data = response.content
                    if len(data) != asset["bytes"] or hashlib.sha256(data).hexdigest() != asset["sha256"]:
                        raise ValueError("Asset checksum mismatch")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(path.suffix + ".part")
                    tmp.write_bytes(data)
                    tmp.replace(path)
            self.assets_ready = True
            self.asset_message = "辨識模型已驗證，可離線使用"
        except Exception as error:
            self.asset_message = "下載失敗（未停用 TLS 驗證）：" + str(error)
        finally:
            self.downloading = False

    def run(self, reachy_mini, stop_event):
        applied = None
        reference_pose = None
        previous = time.monotonic()
        self.ready = True
        self.message = "已連接本機 daemon；尚未啟用動作"
        try:
            while not stop_event.wait(.04):
                now = time.monotonic()
                dt = min(.08, now - previous)
                previous = now
                # Read actual pose, never use a target as evidence that a motor moved.
                pose = reachy_mini.get_current_head_pose()
                _, antennas = reachy_mini.get_current_joint_positions()
                yaw = float(Rotation.from_matrix(pose[:3, :3]).as_euler("xyz", degrees=True)[2])
                measured = {"yaw": yaw, **classroom_antennas(antennas)}
                with self.lock:
                    self.actual = measured
                    if self.enable_requested:
                        self.enable_requested = False
                        rpy = Rotation.from_matrix(pose[:3, :3]).as_euler("xyz", degrees=True)
                        if abs(rpy[0]) > 15 or abs(rpy[1]) > 15 or abs(yaw) > 40:
                            self.disarm("請先在 Control 將 Reachy 喚醒至直立姿勢，再啟用")
                            continue
                        # SDK 1.11 enable_motors pins its targets to the current pose.
                        reachy_mini.enable_motors()
                        self.has_control = True
                        applied = dict(measured)
                        reference_pose = pose.copy()
                        self.desired = None
                        self.armed = True
                        self.last_target = now
                        self.message = "已啟用；等待攝影機或手動目標"
                    if not self.armed:
                        if self.hold_requested:
                            reachy_mini.set_target(head=pose, antennas=antennas)
                            self.hold_requested = False
                        continue
                    if now - self.last_target > .5:
                        reachy_mini.set_target(head=pose, antennas=antennas)
                        self.disarm("輸入逾時 500 ms；保持姿勢，需重新啟用")
                        continue
                    if self.desired is None:
                        continue
                    for name in applied:
                        # Conservative rate: yaw 35°/s, antenna 70°/s.
                        step = (35 if name == "yaw" else 70) * dt
                        applied[name] += float(np.clip(self.desired[name] - applied[name], -step, step))
                    # Preserve measured translation and pitch/roll; replace yaw only.
                    rpy = Rotation.from_matrix(reference_pose[:3, :3]).as_euler("xyz", degrees=True)
                    rpy[2] = applied["yaw"]
                    target_pose = reference_pose.copy()
                    target_pose[:3, :3] = Rotation.from_euler("xyz", rpy, degrees=True).as_matrix()
                    reachy_mini.set_target(head=target_pose, antennas=sdk_antennas(applied))
                    self.message = "追蹤中；影像留在瀏覽器，只有角度送給本機 daemon"
        finally:
            if self.has_control:
                try:
                    reachy_mini.set_target(head=reachy_mini.get_current_head_pose(), antennas=reachy_mini.get_current_joint_positions()[1])
                except Exception:
                    self.logger.warning("Connection lost; could not send final hold")
            self.ready = False
            self.disarm("App 已停止")

if __name__ == "__main__":
    ReachyFollowMe().wrapped_run()
