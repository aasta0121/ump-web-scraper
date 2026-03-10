/**
 * n8n Code node script: CTBA 裁判講習通知
 *
 * 使用方式：
 * 1) 在 n8n 建立 Code node（Run Once for All Items）
 * 2) 貼上本檔內容
 * 3) 建議在 n8n 環境變數設定：
 *    - CTBA_URL（可省略）
 *    - CTBA_KEYWORD（可省略）
 *    - LINE_CHANNEL_ACCESS_TOKEN
 *    - LINE_TO（可多個，逗號或換行）
 */

const CTBA_URL = $env.CTBA_URL || 'http://www.ctba.org.tw/news.php?cate=works&type=16';
const KEYWORD = $env.CTBA_KEYWORD || '裁判講習';
const LINE_TOKEN = $env.LINE_CHANNEL_ACCESS_TOKEN || '';
const LINE_TO_RAW = $env.LINE_TO || '';
const ENABLE_LINE_PUSH = ($env.ENABLE_LINE_PUSH || 'true').toLowerCase() === 'true';

function sha1(text) {
  const crypto = require('crypto');
  return crypto.createHash('sha1').update(text, 'utf8').digest('hex');
}

function parseAnchors(html, baseUrl) {
  const anchors = [];
  const regex = /<a\b[^>]*href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi;
  let match;

  while ((match = regex.exec(html)) !== null) {
    const href = match[1].trim();
    const title = match[2].replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
    if (!title) continue;
    const url = new URL(href, baseUrl).toString();
    anchors.push({ title, url, itemId: sha1(`${title}\n${url}`) });
  }

  return anchors;
}

function parseDateFromTitle(title, now = new Date()) {
  // YYYY/MM/DD or YYYY-MM-DD
  let m = title.match(/(\d{4})[./-](\d{1,2})[./-](\d{1,2})/);
  if (m) {
    const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    if (!Number.isNaN(d.getTime())) return d;
  }

  // 民國 yyy 年 m 月 d 日
  m = title.match(/民國\s*(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日/);
  if (m) {
    const d = new Date(Number(m[1]) + 1911, Number(m[2]) - 1, Number(m[3]));
    if (!Number.isNaN(d.getTime())) return d;
  }

  return null;
}

function isTodayOrYesterday(d, now = new Date()) {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.floor((today - target) / 86400000);
  return diffDays === 0 || diffDays === 1;
}

function parseTargets(raw) {
  return [...new Set(raw.split(/[\n,]+/).map((x) => x.trim()).filter(Boolean))];
}

async function pushLine(to, message, token) {
  const res = await fetch('https://api.line.me/v2/bot/message/push', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      to,
      messages: [{ type: 'text', text: message.slice(0, 5000) }],
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`LINE push failed (${res.status}): ${body}`);
  }
}

async function run() {
  const staticData = $getWorkflowStaticData('global');
  const seenIds = new Set(Array.isArray(staticData.ctbaSeenIds) ? staticData.ctbaSeenIds : []);

  const response = await fetch(CTBA_URL, {
    headers: {
      'User-Agent': 'Mozilla/5.0 (compatible; n8n-ctba-notifier/1.0)',
      'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
    },
  });

  if (!response.ok) {
    throw new Error(`CTBA fetch failed (${response.status})`);
  }

  const html = await response.text();
  const anchors = parseAnchors(html, CTBA_URL);

  const matched = anchors.filter((item) => item.title.includes(KEYWORD));
  const unseen = matched.filter((item) => !seenIds.has(item.itemId));
  const recent = unseen.filter((item) => {
    const d = parseDateFromTitle(item.title);
    return d ? isTodayOrYesterday(d) : false;
  });

  if (recent.length === 0) {
    return [{
      json: {
        ok: true,
        pushed: 0,
        reason: 'No new today/yesterday announcements',
      },
    }];
  }

  const lines = ['【CTBA 新的裁判講習公告】'];
  recent.forEach((item, idx) => {
    lines.push(`${idx + 1}. ${item.title}`);
    lines.push(item.url);
  });
  const message = lines.join('\n');

  const targets = parseTargets(LINE_TO_RAW);
  let pushedCount = 0;

  if (ENABLE_LINE_PUSH) {
    if (!LINE_TOKEN) throw new Error('Missing LINE_CHANNEL_ACCESS_TOKEN');
    if (targets.length === 0) throw new Error('Missing LINE_TO target(s)');

    for (const to of targets) {
      await pushLine(to, message, LINE_TOKEN);
      pushedCount += 1;
    }
  }

  recent.forEach((item) => seenIds.add(item.itemId));
  staticData.ctbaSeenIds = Array.from(seenIds);

  return [{
    json: {
      ok: true,
      pushed: pushedCount,
      targets,
      announcements: recent,
      message,
      linePushEnabled: ENABLE_LINE_PUSH,
    },
  }];
}

return run();
