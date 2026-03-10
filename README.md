# ump-web-scraper

監控中華民國棒球協會（CTBA）指定頁面，當出現新的「裁判講習」公告時，透過 LINE Messaging API 推播通知。

## 功能

- 抓取 `http://www.ctba.org.tw/news.php?cate=works&type=16`
- 解析頁面中的連結文字，篩選包含「裁判講習」的公告
- 只推播「今天或昨天」日期的公告（可用參數關閉）
- 透過本地狀態檔避免重複通知
- 發現新公告時，推播到 LINE（Bot push message）
- 支援多個 `LINE_TO` 目標（逗號或換行分隔）

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


## 環境檔（.env）

你可以直接複製範例檔：

```bash
cp .env.example .env
```

再把 `.env` 內的 `LINE_CHANNEL_ACCESS_TOKEN` / `LINE_TO` 改成你的值，或改用 `*_FILE` 路徑模式。

## 環境變數

- `CTBA_URL`：監控網址（預設 `http://www.ctba.org.tw/news.php?cate=works&type=16`）
- `CTBA_KEYWORD`：關鍵字（預設 `裁判講習`）
- `STATE_FILE`：狀態檔路徑（預設 `state/ctba_seen.json`）
- `LINE_CHANNEL_ACCESS_TOKEN`：LINE Bot token
- `LINE_CHANNEL_ACCESS_TOKEN_FILE`：token 檔案路徑（可替代上面環境變數）
- `LINE_TO`：推播對象（可放多個，逗號或換行分隔）
- `LINE_TO_FILE`：推播對象檔案路徑（可替代 `LINE_TO`）

## 把 LINE key 另外放在檔案（建議）

建立兩個檔案：

```bash
mkdir -p secrets
printf '%s' 'YOUR_LINE_CHANNEL_ACCESS_TOKEN' > secrets/line_token.txt
cat > secrets/line_to.txt <<'EOF'
Uxxxxxxxxxxxxxxx
Cxxxxxxxxxxxxxxx
EOF
```

執行時指定檔案即可：

```bash
python ctba_notifier.py \
  --line-token-file secrets/line_token.txt \
  --line-to-file secrets/line_to.txt
```

> 建議把 `secrets/` 加到 `.gitignore`，避免把 token push 到 git。

## `LINE_TO` 可以群發嗎？

可以。此工具支援你在 `LINE_TO`（或 `LINE_TO_FILE`）填多個 target，程式會逐一推播：

```bash
export LINE_TO='Uxxxx,Cyyyy,Gzzzz'
python ctba_notifier.py --line-token-file secrets/line_token.txt
```

注意：這是「逐一 push 到多個 to ID」，不是 LINE 的 broadcast API（broadcast 不需要 `to`，權限與額度規則不同）。

## 日期過濾規則（今天 / 昨天）

預設情況下，只會通知標題內可解析出日期，且日期為「今天」或「昨天」的公告。

支援常見日期格式（從標題解析）：

- `2026/01/05`
- `2026-01-05`
- `民國 115 年 1 月 5 日`
- `01/05`（會嘗試用最接近今天的年份）

若你想暫時關閉此限制（改成所有新公告都通知），可加上：

```bash
python ctba_notifier.py --disable-date-filter
```

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
