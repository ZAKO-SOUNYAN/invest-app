"""gmail_notifier.py — Gmailを使ったメール通知機能"""

import smtplib
import pandas as pd
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from typing import Optional


def send_gmail(
    gmail_address: str,
    app_password: str,
    to_address: str,
    result_df: pd.DataFrame,
    min_score: int = 0,
) -> tuple[bool, str]:
    """
    スクリーニング結果をGmailで送信する。

    Args:
        gmail_address: 送信元のGmailアドレス
        app_password:  Googleアプリパスワード（16文字）
        to_address:    送信先メールアドレス
        result_df:     スクリーニング結果のDataFrame
        min_score:     通知するスコアの下限

    Returns:
        (success: bool, message: str)
    """
    if result_df.empty:
        return False, "通知する銘柄がありません。"

    # スコアでフィルタ
    df = result_df.copy()
    df["_score_int"] = pd.to_numeric(df["スコア"], errors="coerce").fillna(0).astype(int)
    df = df[df["_score_int"] >= min_score].sort_values("_score_int", ascending=False)

    if df.empty:
        return False, f"スコア{min_score}点以上の銘柄がありません。"

    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")

    # ── HTMLメール本文 ──
    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ font-family: sans-serif; background: #f5f5f5; padding: 20px; }}
  .container {{ background: white; border-radius: 8px; padding: 24px;
                max-width: 700px; margin: 0 auto; }}
  h2 {{ color: #1a237e; border-bottom: 2px solid #1a237e; padding-bottom: 8px; }}
  .meta {{ color: #666; font-size: 13px; margin-bottom: 16px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ background: #1a237e; color: white; padding: 10px 8px; text-align: left; }}
  td {{ padding: 9px 8px; border-bottom: 1px solid #eee; }}
  tr:hover {{ background: #f5f5f5; }}
  .score-green  {{ background:#e8f5e9; color:#1b5e20; font-weight:bold;
                   border-radius:4px; padding:2px 6px; }}
  .score-yellow {{ background:#fff8e1; color:#f57f17; font-weight:bold;
                   border-radius:4px; padding:2px 6px; }}
  .score-orange {{ background:#fbe9e7; color:#bf360c; font-weight:bold;
                   border-radius:4px; padding:2px 6px; }}
  .footer {{ font-size: 12px; color: #999; margin-top: 20px; }}
</style>
</head>
<body>
<div class="container">
  <h2>📈 成長株スクリーニング結果</h2>
  <p class="meta">スキャン日時: {now}　／　ヒット件数: {len(df)}銘柄（スコア{min_score}点以上）</p>
  <table>
    <tr>
      <th>銘柄コード</th>
      <th>銘柄名</th>
      <th>現在値</th>
      <th>スコア</th>
      <th>判定</th>
      <th>売上高成長率</th>
      <th>EPS</th>
      <th>25日乖離率</th>
      <th>配当利回り</th>
    </tr>
"""
    for _, row in df.iterrows():
        score_val = row["_score_int"]
        if score_val >= 75:
            score_cls = "score-green"
        elif score_val >= 55:
            score_cls = "score-yellow"
        else:
            score_cls = "score-orange"

        html += f"""
    <tr>
      <td><b>{row.get('銘柄コード','')}</b></td>
      <td>{row.get('銘柄名','')}</td>
      <td>{row.get('現在値','')}</td>
      <td><span class="{score_cls}">{score_val}点</span></td>
      <td>{row.get('判定','')}</td>
      <td>{row.get('売上高成長率','')}</td>
      <td>{row.get('EPS','')}</td>
      <td>{row.get('25日乖離率','')}</td>
      <td>{row.get('配当利回り','')}</td>
    </tr>"""

    html += """
  </table>
  <p class="footer">
    ⚠️ 本メールは情報提供を目的としており、投資助言ではありません。<br>
    投資判断はご自身の責任において行ってください。
  </p>
</div>
</body>
</html>
"""

    # ── プレーンテキスト（HTMLが表示できない場合の代替） ──
    plain = f"成長株スクリーニング結果 ({now})\n"
    plain += f"ヒット: {len(df)}銘柄（スコア{min_score}点以上）\n\n"
    for _, row in df.iterrows():
        plain += (f"{row.get('銘柄コード','')} {row.get('銘柄名','')} "
                  f"スコア:{row['_score_int']}点 {row.get('判定','')}\n")
    plain += "\n⚠️ 投資助言ではありません。"

    # ── メール送信 ──
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📈 成長株シグナル {len(df)}件ヒット ({now[:10]})"
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
    except smtplib.SMTPException as e:
        return False, f"送信エラー：{str(e)[:80]}"
    except Exception as e:
        return False, f"エラー：{str(e)[:80]}"


def send_test_gmail(
    gmail_address: str,
    app_password: str,
    to_address: str,
) -> tuple[bool, str]:
    """テスト用のメールを送信する。"""
    test_df = pd.DataFrame([{
        "銘柄コード":   "7203",
        "銘柄名":       "テスト銘柄",
        "現在値":       "¥3,000",
        "スコア":       80,
        "判定":         "🟢 強い買い",
        "売上高成長率": "+25.0%",
        "EPS":          "↑増加",
        "25日乖離率":   "+3.0%",
        "配当利回り":   "2.50%",
        "カップ":       "✅",
    }])
    return send_gmail(gmail_address, app_password, to_address, test_df, min_score=0)
