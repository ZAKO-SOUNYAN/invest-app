"""gmail_notifier.py — Gmail通知機能"""

import smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime


def send_gmail(gmail_address: str, app_password: str, to_address: str,
               result_df: pd.DataFrame, min_score: int = 0) -> tuple[bool, str]:
    if result_df.empty:
        return False, "通知する銘柄がありません。"

    df = result_df.copy()
    df["_s"] = pd.to_numeric(df["スコア"], errors="coerce").fillna(0).astype(int)
    df = df[df["_s"] >= min_score].sort_values("_s", ascending=False)
    if df.empty:
        return False, f"スコア{min_score}点以上の銘柄がありません。"

    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    rows = ""
    for _, row in df.iterrows():
        s = row["_s"]
        bg = "#1b5e20" if s>=75 else ("#f9a825" if s>=55 else "#bf360c")
        fg = "white"   if s>=75 else ("black"   if s>=55 else "white")
        rows += f"""<tr>
          <td style="padding:8px;font-weight:bold">{row.get('銘柄コード','')}</td>
          <td style="padding:8px">{row.get('銘柄名','')}</td>
          <td style="padding:8px;text-align:right">{row.get('現在値','')}</td>
          <td style="padding:8px;text-align:center">
            <span style="background:{bg};color:{fg};padding:2px 8px;border-radius:4px;font-weight:bold">
              {s}点
            </span>
          </td>
          <td style="padding:8px">{row.get('判定','')}</td>
          <td style="padding:8px;text-align:right">{row.get('25日乖離率','')}</td>
          <td style="padding:8px;text-align:right">{row.get('配当利回り','')}</td>
        </tr>"""

    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"></head>
<body style="background:#0a0e1a;color:#e0e0e0;font-family:sans-serif;padding:20px">
<div style="max-width:720px;margin:0 auto;background:#0d1117;border-radius:12px;
            padding:24px;border:1px solid #00ff88">
  <h2 style="color:#00ff88;margin:0 0 4px">📈 成長株スクリーニング結果</h2>
  <p style="color:#888;margin:0 0 20px;font-size:13px">
    {now} ／ {len(df)}銘柄ヒット（スコア{min_score}点以上）
  </p>
  <table style="width:100%;border-collapse:collapse;font-size:14px">
    <thead>
      <tr style="background:#1a1f2e;color:#00ff88">
        <th style="padding:10px;text-align:left">コード</th>
        <th style="padding:10px;text-align:left">銘柄名</th>
        <th style="padding:10px;text-align:right">現在値</th>
        <th style="padding:10px;text-align:center">スコア</th>
        <th style="padding:10px;text-align:left">判定</th>
        <th style="padding:10px;text-align:right">乖離率</th>
        <th style="padding:10px;text-align:right">配当</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
  <p style="font-size:11px;color:#555;margin-top:20px">
    ⚠️ 本メールは情報提供を目的としており、投資助言ではありません。
  </p>
</div>
</body></html>"""

    plain = f"成長株スクリーニング結果 ({now})\n{len(df)}銘柄\n\n"
    for _, row in df.iterrows():
        plain += f"{row.get('銘柄コード','')} {row.get('銘柄名','')} {row['_s']}点 {row.get('判定','')}\n"

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📈 成長株シグナル {len(df)}件 ({now[:10]})"
        msg["From"]    = gmail_address
        msg["To"]      = to_address
        msg.attach(MIMEText(plain, "plain", "utf-8"))
        msg.attach(MIMEText(html,  "html",  "utf-8"))
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(gmail_address, app_password)
            smtp.sendmail(gmail_address, to_address, msg.as_string())
        return True, f"{len(df)}銘柄の結果をメールで送信しました。"
    except smtplib.SMTPAuthenticationError:
        return False, "認証エラー：GmailアドレスまたはアプリパスワードGが正しくありません。"
    except Exception as e:
        return False, f"送信エラー：{str(e)[:80]}"


def send_test_gmail(gmail_address: str, app_password: str,
                    to_address: str) -> tuple[bool, str]:
    test_df = pd.DataFrame([{
        "銘柄コード": "7203", "銘柄名": "テスト銘柄",
        "現在値": "¥3,000", "スコア": 80,
        "判定": "🟢 強い買い", "25日乖離率": "+3.0%", "配当利回り": "2.50%",
    }])
    return send_gmail(gmail_address, app_password, to_address, test_df, min_score=0)
