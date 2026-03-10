# ump-web-scraper

這個專案已改為 **n8n Code node 版本**。`ctba_notifier.py` 內容是可直接貼到 n8n Code node 執行的 JavaScript。

## 你要的功能

- 抓取 CTBA 頁面：`http://www.ctba.org.tw/news.php?cate=works&type=16`
- 篩選標題含「裁判講習」
- 只通知「今天或昨天」日期的公告
- 透過 LINE Push API 發送通知
- 用 n8n workflow static data 記錄已通知項目（避免重複）
- `LINE_TO` 可多個目標（逗號或換行）

## 在 n8n 使用

1. 建立一個 `Code` node（建議 `Run Once for All Items`）。
2. 把 `ctba_notifier.py` 內容整段貼進去。
3. 在 n8n 環境變數設定：

```env
CTBA_URL=http://www.ctba.org.tw/news.php?cate=works&type=16
CTBA_KEYWORD=裁判講習
LINE_CHANNEL_ACCESS_TOKEN=你的token
LINE_TO=Uxxxx,Cyyyy,Gzzzz
ENABLE_LINE_PUSH=true
```

> 若只想測試不發送 LINE，可把 `ENABLE_LINE_PUSH=false`。

## 輸出結果

Code node 會回傳一筆 JSON，包含：

- `ok`
- `pushed`（實際推播數）
- `targets`
- `announcements`
- `message`
- `linePushEnabled`

## 注意

- 檔名雖是 `.py`，但內容是給 n8n Code node 使用的 JavaScript。
- 若 CTBA 站台擋 request（403），請改由可連通的 n8n 執行環境跑。
