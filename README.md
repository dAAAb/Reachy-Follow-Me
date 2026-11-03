---
title: Reachy Follow Me
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: static
app_file: index.html
pinned: false
short_description: Local webcam teleoperation for Reachy Mini Control.
license: apache-2.0
tags:
  - reachy_mini
  - reachy_mini_python_app
  - teleoperation
---

# Reachy Follow Me

台大「虛擬人與遙現」2026 第九週：**頭部與雙手 → Reachy Mini 頭部與天線**。

兩種執行方式共用相同映射：

- **無硬體**：官方 Reachy Mini XML、MuJoCo 與解析式 IK；不是手繪替代外形。
- **Reachy Mini Control App**：正式 `ReachyMiniApp` Python 套件與 `reachy_mini_apps` entrypoint。由 Control / daemon 安裝、啟動、停止，經官方 SDK 操作實體 Reachy。

## 安裝到 Reachy Mini Control

在 Control 的社群 Apps / Install from Hugging Face 尋找 **dAAAb / Reachy-Follow-Me**。安裝後 Run，開啟齒輪設定；或在同一台電腦的 Chrome 開啟 http://127.0.0.1:8043 。不同 Control 版本可能需要選擇「所有社群 App」而非官方精選。

這版優先支援 **Mac／PC 上執行的 Control 與本機 daemon**，使用電腦固定攝影機。啟動 App 不會自動開馬達控制，也不會探索其他 LAN 機器人。

1. 第一次按「下載辨識模型（約 60 MB）」，下載固定版本並驗證 SHA-256。完成後可離線。
2. 按「開啟攝影機」。預覽只有 video，不開麥克風；影像在自己的瀏覽器辨識。
3. 頭部正面看鏡頭，按「頭部歸中」。讓雙肩與手腕入鏡。
4. 先確保 Reachy 已在 Control 喚醒、直立、周圍無障礙。按「啟用 Reachy 並接手」。App 先讀取目前姿勢，保留位置與 pitch/roll，只調整 yaw 與天線。
5. 人的右手升高 → **機器人自己的左天線**升高；正面觀察是在畫面右側。鏡像模式的頭部轉向也使用同一規則。
6. 停止、分頁進背景或輸入超過 500 ms 未更新時保持姿勢，必須重新啟用。不會直接斷扭力使機器人倒下。

無法從清單找到時，可在 **Control 實際使用的 Python 環境**安裝：

```sh
python -m pip install git+https://github.com/dAAAb/Reachy-Follow-Me.git
```

重新整理／重啟 daemon 後，安裝清單應出現 `reachy_follow_me`。不要裝到另一個無關的 Python 環境。開發模式可在 repo 根目錄 `python -m pip install -e .`。

### Wireless

App 也可由 Wireless 的 daemon 執行，但設定伺服器刻意只綁 `127.0.0.1:8043`。請用自己的既有 SSH 帳號建立本機轉接，例如：

```sh
ssh -N -L 8043:127.0.0.1:8043 pollen@reachy-mini.local
```

然後仍在電腦開 http://127.0.0.1:8043 ，使用電腦的固定鏡頭。這能保留 getUserMedia 的 localhost 安全來源，不需公開馬達 API 或停用瀏覽器安全設定。**Wireless 安裝與實機動作尚待該硬體驗證**；本版沒有把跟著動的機器人鏡頭誤當成固定參考鏡頭。

## 不接硬體：官方 MuJoCo

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-mujoco.txt
.venv/bin/python scripts/setup_assets.py
.venv/bin/python server.py
```

Chrome 開 http://127.0.0.1:8099 。Windows 將 `.venv/bin/python` 改為 `.venv\Scripts\python`。此模式不連 daemon、不探索 LAN、不碰實體機器人。手動滑桿與合成範例不需先下載辨識模型。

按「合成範例」看人工座標重播，再試攝影機。0 / 150 / 400 ms 延遲、抖動與丟包供課堂觀察。命令年齡不是完整 camera-to-motor 延遲。官方模擬器使用本機安裝的 Reachy Mini 1.11.0／MuJoCo 3.3.0。

## 左右與單位契約

| 輸入 | 目標 | 邊界 |
|---|---|---|
| MediaPipe column-major face matrix yaw | Reachy Z-up yaw | ±35°，歸中後鏡像變號 |
| 人體右手腕高於右肩 | 機器人左天線 | 教學角度 0–70° |
| 人體左手腕高於左肩 | 機器人右天線 | 教學角度 0–70° |

0° 表示向外放低，70° 表示直立。關鍵點左右是人體解剖側，CSS 只鏡像預覽；不要再交換兩次。取消鏡像後，頭與天線一同切換為同側模仿。

SDK 天線順序是 **`[right, left]`，單位 radian**；SDK 的 MuJoCo backend 又會把天線符號取負。`reachy_follow_me/adapter.py` 把這件事寫成單一契約，模擬與實體共用，並以 actuator 名稱查找，不依賴陣列順序猜左右。

單軸按鈕可分別驗證頭部、左天線、右天線。頭與手分開做信心門檻；看不到手時不亂動該天線，仍可追蹤頭部。

## 開發與驗證

```sh
python scripts/prepare_app.py
node --test tests/*.test.mjs
python -m unittest discover -s tests -p 'test_*.py'
reachy-mini-app-assistant check .
python scripts/audit_public.py
```

`prepare_app.py` 只同步已審查的前端文字檔到套件；不含模型、攝影機資料或本機設定。模型下載到使用者快取，不寫 repo。`server.py` 是獨立 MuJoCo 教室版；`reachy_follow_me/main.py` 是 Control 的正式 App。

目前驗證：官方 MuJoCo 畫面、單軸左右、16 個 JS 測試、5 個 Python App 測試；官方 app-assistant 完整安裝／移除檢查通過，已由官方模擬 daemon App manager 啟動。USB／Wireless 實體環境、不同人的攝影機姿勢需實機驗收；人工座標與 mock SDK 不能代表所有硬體已驗證。


### 追蹤離開畫面

畫面邊界會額外檢查，不能只相信模型的 visibility。整隻手臂看不到就保持，回到框內連續三幀穩定後，模擬器以平滑和限速接續；只有手掌看不到時，肩肘繼續，手腕與夾爪保持。實體控制失去有效輸入後鎖住 HOLD，必須明確重新啟用，避免重新入鏡突然動作。

## 隱私

沒有 API Key、雲端推論、遙測或自動機器人探索。影像留在瀏覽器；只有三個有界角度送往本機 App。下載時會連 Google／jsDelivr；執行資源本機供應。拒絕不符 Host、跨來源寫入與無效角度。不將 localhost 伺服器公開到 Internet。

不要提交 `.env`、錄影、校正檔、SSH 憑證、個人路徑。來源授權見 `NOTICE`、`LICENSES/`；公開檢查見 `SECURITY.md`。

- [官方 App 發佈方式](https://huggingface.co/blog/pollen-robotics/make-and-publish-your-reachy-mini-apps)
- [Reachy Mini SDK](https://github.com/pollen-robotics/reachy_mini)
- [MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/web_js)
