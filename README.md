# Reachy Follow Me

**台大「虛擬人與遙現」2026 第九週：用自己的身體，操控另一個身體。**

鏡頭估計頭部左右旋轉與雙手抬高程度，讓 Reachy Mini 模擬器跟著動。預設採鏡像互動：**人的右手 → 機器人自己的左天線**。相對站立時，這支天線在觀眾的畫面右側。

**預設直接顯示官方 Reachy Mini 的 MuJoCo 物理模擬。** 使用官方 XML、機械模型與解析式 IK，不提供手繪替代外形，也不會連實體機器人。

## 啟動（不用硬體、不用 API Key）

需要 Python 3.12、近期 Chrome／Chromium 與可供 MuJoCo 使用的圖形環境。目前實測環境為 Apple Silicon Mac + Chrome；其他平台請先驗證 MuJoCo 的渲染驅動。

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-mujoco.txt
.venv/bin/python scripts/setup_assets.py
.venv/bin/python server.py
```

Windows 請將 `.venv/bin/python` 改成 `.venv\Scripts\python`。開啟終端機顯示的 `http://127.0.0.1:8099`。
第一次下載約 60 MB 的固定版本 MediaPipe Tasks Vision 1.2.0 WASM 與官方 face/pose/hand 模型；每個檔案以 SHA-256 驗證。下載完成後，不需雲端推論，斷網也可使用。HTTP 層只用 Python 標準函式庫；官方物理模擬需上述 SDK / MuJoCo 依賴。

1. 按 **合成範例**：先確認顯示、映射與停止功能。這是人工座標，不是真人影像。
2. 按 **開啟攝影機**，允許本機網站使用相機。此時仍是 STOP。
3. 確認橘色標記在自己的右手腕；讓肩膀、手肘和手腕入鏡。光線足、背景單純時較穩定。
4. 按 **接手／繼續**。畫面看不到手、信心不足或相機中斷時，不產生新手部目標。
5. 按 **停止（Space）** 清掉所有排程；再次接手才恢復。切到背景分頁也會停止。
6. 結束請按 **關閉鏡頭**，或關閉分頁；終端機 Ctrl+C 關閉伺服器。

如果不開鏡頭，手動滑桿與合成範例都不需先下載辨識模型。模型下載不是啟動伺服器的必要條件。

## 延遲實驗（8–10 分鐘）

固定同一個手勢，依序比較 0 / 150 / 400 ms 指令延遲，再加 ±100 ms 抖動或 20% 丟包。觀察目標、Follower 與自己的動作是否同步。選 100% 丟包，確認 HOLD；按停止，確認之前排隊的命令不會在稍後突然出現。

記錄三件事：主觀難度、命令年齡、停止是否可靠。畫面上的「命令年齡」從本機送出目標起算，**不等於完整攝影機到馬達延遲**；也不包含實體視訊回傳。辨識耗時只量測當次 MediaPipe 呼叫。

匯出紀錄只含相對時間、模式、狀態、目標套用角度與命令年齡，最多保留 6,000 筆。沒有影像、聲音、姓名或人體關鍵點。

## 控制迴路

```text
Camera → MediaPipe landmarks → retarget / normalize
       → confidence gate → bounded target → delayed channel
       → timestamp ordering → rate limit + EMA → simulated body
                                                    ↓
                                    visible feedback to human
```

角度使用 degree；實際渲染／IK 邊界才換成 radian。EMA 時間常數 90 ms、前端速度上限 120°/s，命令超過 350 ms 沒有到達就 HOLD（保持姿勢）。這些是課堂實驗值，不是硬體安全規格。若改接實體機器人，需要重新設計硬體急停、制動、碰撞、限位與 watchdog；本版本沒有這種連線功能。

## 程式入口

- `web/control-core.js`：可單獨測試的映射與控制器。
- `web/vision.js`：本機 MediaPipe；相機資料不離開瀏覽器。
- `web/lab.js`：輸入來源、畫面、延遲實驗與本機紀錄。
- `server.py`：只服務 `web/`；不提供檔案上傳或任意檔案讀取。
- `assets-manifest.json`：下載來源、版本、大小、SHA-256。

```sh
node --test tests/*.test.mjs
```

測試涵蓋左右映射、失去關鍵點、NaN、角度與速度上限、封包亂序、逾時、停止後不重播舊命令。人工座標測試不代表所有真人、相機或姿勢都辨識可靠。

## 隱私與公開範圍

本專案沒有 API Key、登入、遙測、雲端影像上傳、實體機器人探索，也不讀取任何個人設定。相機只開 video，不開麥克風。安裝時的模型下載會連到 Google 與 jsDelivr；執行時的應用資源都來自 localhost。不要把伺服器公開到網際網路，也不要用 tunnel 直接暴露；本版沒有帳號權限層。

請勿把 `.env`、錄影、個人相機畫面、校正檔或帳號資料 commit 上來。`SECURITY.md` 說明公開前的檢查方式。原始範例與第三方授權見 `NOTICE`、`LICENSES/`。

## 官方 MuJoCo 模擬器

以 Python 3.12 在獨立環境安裝（本次實測 reachy-mini 1.11.0、MuJoCo 3.3.0）：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-mujoco.txt
.venv/bin/python server.py --mujoco
```

Windows 使用 `.venv\Scripts\python`。頁面預設顯示官方 MuJoCo；瀏覽器送出的只有三個有界角度與 active 狀態，圖片是模擬器渲染畫面，不是攝影機影像。

### 映射與左右

| 觀測 | 控制目標 | 限制 |
|---|---|---|
| 臉部 transformation matrix 的 yaw | 頭部 yaw | ±35°；可歸中／反轉 |
| 右手腕相對右肩高度 | 左天線 | 0–70° |
| 左手腕相對左肩高度 | 右天線 | 0–70° |

頭部與手部分別判定信心：手離開鏡頭時天線保持，頭仍可跟隨。手部尺度優先用肩到髖距，髖不在畫面時使用教學近似尺度，故不應解讀為量測儀器。

0° 是教學定義的天線向外放低，70° 是向上；不是原廠馬達零點。SDK 使用 `[right, left]` 的命令慣例，而不同版本模型/註解的排列可能不同；`simulator.py` **按 actuator 名稱**尋找 `left_antenna` / `right_antenna`，不依賴固定陣列索引。左右鉸鏈轉向亦相反。MuJoCo 收到最後命令 500 ms 後停止更新目標；每次最多 100°/s。

單人、正面、上半身完整入鏡最適合。Face Landmarker 不是醫療級頭部追蹤，帽子、遮擋、側臉和鏡頭差異都可能影響結果。請先轉頭測試方向，必要時勾選反轉，再做課堂示範。

## 來源

- [Reachy Mini](https://github.com/pollen-robotics/reachy_mini)：官方模型、SDK 與座標概念。
- [MediaPipe Face Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/web_js)
- [MediaPipe Pose Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/pose_landmarker/web_js)

本專案獨立製作，非 Pollen Robotics 官方產品。
