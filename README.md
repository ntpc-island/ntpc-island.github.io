# 新北政見島（非官方原型）

把蘇巧慧 2026 新北市長競選網站（[chiao.tw/policies](https://chiao.tw/policies)）的 14 項政見，做成 3D 互動島嶼：14 座六角形島拼成一整座新北島，周圍有河流、環狀線、稻田與 12 個新北景點，點選島嶼會顯示政見摘要並連回官網原文。

- **非官方作品**，內容摘錄於 2026-10-22，以官方網站為準
- 單一 `index.html`，透過 import map 從 jsDelivr 載入 Three.js r160，無建置步驟
- 所有模型都是用 Three.js 基本幾何體以程式生成，不載入外部模型檔

## 本機執行

```bash
python3 -m http.server 8000
# 開啟 http://localhost:8000
```

## 由政見資料產生的靜態檔

修改 `index.html` 裡的 `POLICIES` 或 `SPOTS` 後，要重新產生：

```bash
python3 tools/build_static.py
```

會更新這些檔案：

- `policy/`、`spot/`、`about/`：給搜尋引擎與一般閱讀的文字頁。3D 網站把所有內容放在同一個網址的 `#` 後面，搜尋引擎只會當成一頁，所以每項政見與景點另有自己的頁面。共用樣式在 `pages.css`。
- `share/*.html`：每項政見與景點的分享預覽頁。社群平台抓預覽時看不到網址 `#` 後面的部分，所以每項都有自己的頁面帶標題與摘要，打開後跳回主頁面（保留 `utm_*` 參數供 GA4 判斷來源）。
- `index.html` 裡 `seo:jsonld` 與 `seo:noscript` 標記之間的內容：給搜尋引擎讀的結構化資料與文字版政見。
- `sitemap.xml`

`og.png` 是首頁與總覽頁共用的 1200×630 封面（左邊標題與功能、右邊政見島，網站自己畫：`index.html?og=cover`）。`hero.jpg` 是 3D 載入前先顯示的靜態全景圖，同樣由 `build_og_images.py` 產生。每項政見與景點的預覽卡片在 `og/`，由網站自己畫（`index.html?og=policy-12`）再截圖，需要 agent-browser。內容或外觀改了之後：

```bash
python3 tools/build_og_images.py && python3 tools/build_static.py
```

## 流量統計

使用 Google Analytics 4（`G-5H13CQWF3X`）。除了頁面瀏覽，還記錄 `view_policy`、`view_spot`、`share`、`search`、`filter_category`、`open_index` 事件。

## 官方政見更新偵測

非官方整理最大的風險是內容過時。`.github/workflows/check-source.yml` 每天 09:00（台北時間）執行 `tools/check_source.py`，把官網政見頁的內文和 `tools/source_snapshot.json` 比對，有新增、移除或內容變更就開一張標籤為 `source-changed` 的 issue。

收到通知後：

1. 對照官網，更新 `index.html` 的 `POLICIES` 與 `SOURCE_DATE`
2. `python3 tools/check_source.py --update`
3. `python3 tools/build_og_images.py && python3 tools/build_static.py`

`source_snapshot.json` 的官方原文也是「地區」分頁的資料來源：`build_static.py` 會找出每項政見原文裡點名了哪些行政區。

## 更新紀錄

網站上的「更新紀錄」（`/updates/`）由 `tools/releases.json` 產生，一天一筆、最新的放最上面。內容寫給一般訪客看：說明大家能做什麼，不寫技術細節。

新增一天的更新：

1. 在 `tools/releases.json` 最前面加一筆 `{ "date", "title", "items": [{ "title", "desc" }] }`；某項由其他人貢獻時，可以在該項加上 `"credit": { "name", "url" }`，頁面會顯示「感謝 @name 貢獻」
2. `python3 tools/build_static.py`

最新一筆也會嵌進首頁：之前來過、但還沒看過這次更新的訪客，進站時會看到一行「10/23 更新：…」的提示。

## 自動產生（GitHub Actions）

`.github/workflows/build.yml`：推送到 `main` 且改到 `index.html`、`pages.css` 或 `tools/` 時，會在 GitHub 上用無頭 Chromium 重新產生預覽圖、分享頁、文字頁與 sitemap，有變動就自動 commit。一般改內容只要推上去即可，不必在本機跑工具。

預覽圖在 `?og=` 模式下使用固定亂數、場景靜止，同樣的程式會畫出同樣的圖，所以沒有實際改動時不會產生新的 commit。

## 選舉期間

`tools/election.json` 記錄投票日與資料來源（產生 `/vote/` 投票資訊頁），`quiet_dates` 列出的日期（台北時間）網站會暫停分享按鈕、圖卡與首次提示，只保留閱讀。網址加 `?quiet=1` 可預覽這個模式。

