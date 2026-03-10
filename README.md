# ump-web-scraper

監控中華民國棒球協會（CTBA）指定頁面，當出現新的「裁判講習」公告時，透過 LINE Messaging API 推播通知。

## 功能

- 抓取 `http://www.ctba.org.tw/news.php?cate=works&type=16`
- 解析頁面中的連結文字，篩選包含「裁判講習」的公告
- 透過本地狀態檔避免重複通知
- 發現新公告時，推播到 LINE（Bot push message）

## 需求

- Python 3.10+
- 可連外網路（存取 CTBA 與 LINE API）
- 一組 LINE Messaging API Channel access token
- 目標 `to` ID（使用者、群組或聊天室 ID）

## 快速開始

```bash
python ctba_notifier.py --dry-run
```

第一次建議使用 `--dry-run`，先確認抓到的資料是否正確。

## 環境變數

- `CTBA_URL`：監控網址（預設 `http://www.ctba.org.tw/news.php?cate=works&type=16`）
- `CTBA_KEYWORD`：關鍵字（預設 `裁判講習`）
- `STATE_FILE`：狀態檔路徑（預設 `state/ctba_seen.json`）
- `LINE_CHANNEL_ACCESS_TOKEN`：LINE Bot token
- `LINE_TO`：推播對象 ID

## 正式執行

```bash
export LINE_CHANNEL_ACCESS_TOKEN='YOUR_TOKEN'
export LINE_TO='YOUR_TARGET_ID'
python ctba_notifier.py
```

## 建議排程（crontab）

每 30 分鐘檢查一次：

```cron
*/30 * * * * cd /workspace/ump-web-scraper && /usr/bin/python3 ctba_notifier.py >> cron.log 2>&1
```

## 測試

```bash
python -m unittest discover -s tests -p 'test_*.py'
```
