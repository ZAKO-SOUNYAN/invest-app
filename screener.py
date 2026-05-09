"""screener.py — スクリーニングロジック（プリセットモード対応）"""

import pandas as pd
import numpy as np
import time
import random
from dataclasses import dataclass, field
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from data_loader import fetch_price_history, calc_indicators

MAX_WORKERS = 3

# ──────────────────────────────────────────────
# 会社名辞書（検索用）
# ──────────────────────────────────────────────
COMPANY_DICT = {
    "ソニーグループ":               "6758.T",
    "キーエンス":                   "6861.T",
    "トヨタ自動車":                 "7203.T",
    "ソフトバンクグループ":         "9984.T",
    "東京エレクトロン":             "8035.T",
    "ファナック":                   "6954.T",
    "デンソー":                     "6902.T",
    "ダイキン工業":                 "6367.T",
    "京セラ":                       "6971.T",
    "日立製作所":                   "6501.T",
    "アドバンテスト":               "6857.T",
    "ルネサスエレクトロニクス":     "6723.T",
    "信越化学工業":                 "4063.T",
    "ニデック":                     "6594.T",
    "スクリーンHD":                 "7735.T",
    "パナソニックHD":               "6752.T",
    "NEC":                          "6701.T",
    "富士通":                       "6702.T",
    "オムロン":                     "6645.T",
    "太陽誘電":                     "6976.T",
    "村田製作所":                   "6981.T",
    "ローム":                       "6963.T",
    "イビデン":                     "4062.T",
    "ディスコ":                     "6146.T",
    "HOYA":                         "7741.T",
    "富士フイルムHD":               "4901.T",
    "キヤノン":                     "7751.T",
    "オリンパス":                   "7733.T",
    "ニコン":                       "7731.T",
    "NTT":                          "9432.T",
    "KDDI":                         "9433.T",
    "ソフトバンク":                 "9434.T",
    "JR東日本":                     "9020.T",
    "JR東海":                       "9022.T",
    "JR西日本":                     "9021.T",
    "東京ガス":                     "9531.T",
    "大阪ガス":                     "9532.T",
    "三菱UFJ FG":                   "8306.T",
    "三井住友FG":                   "8316.T",
    "みずほFG":                     "8411.T",
    "野村HD":                       "8604.T",
    "MS&AD":                        "8725.T",
    "第一生命HD":                   "8750.T",
    "東京海上HD":                   "8766.T",
    "SOMPOホールディングス":        "8630.T",
    "大和証券G":                    "8601.T",
    "日本取引所G":                  "8697.T",
    "ファーストリテイリング":       "9983.T",
    "セブン&アイHD":                "3382.T",
    "イオン":                       "8267.T",
    "味の素":                       "2802.T",
    "JT":                           "2914.T",
    "ZOZO":                         "3092.T",
    "ローソン":                     "2651.T",
    "ABCマート":                    "2670.T",
    "くら寿司":                     "2695.T",
    "マクドナルドHD":               "2702.T",
    "中外製薬":                     "4519.T",
    "第一三共":                     "4568.T",
    "武田薬品工業":                 "4502.T",
    "シスメックス":                 "6869.T",
    "テルモ":                       "4543.T",
    "塩野義製薬":                   "4507.T",
    "エーザイ":                     "4523.T",
    "久光製薬":                     "4530.T",
    "三井不動産":                   "8801.T",
    "三菱地所":                     "8802.T",
    "大和ハウス工業":               "1925.T",
    "積水ハウス":                   "1928.T",
    "オープンハウスG":              "3288.T",
    "住友不動産":                   "8830.T",
    "野村不動産HD":                 "3231.T",
    "ヒューリック":                 "3003.T",
    "ホンダ":                       "7267.T",
    "マツダ":                       "7261.T",
    "スズキ":                       "7269.T",
    "SUBARU":                       "7270.T",
    "ヤマハ発動機":                 "7272.T",
    "日産自動車":                   "7201.T",
    "三菱ケミカルG":                "4188.T",
    "三井化学":                     "4183.T",
    "住友化学":                     "4005.T",
    "日産化学":                     "4021.T",
    "ENEOSホールディングス":        "5020.T",
    "ブリヂストン":                 "5108.T",
    "大成建設":                     "1801.T",
    "大林組":                       "1802.T",
    "清水建設":                     "1803.T",
    "鹿島建設":                     "1812.T",
    "アサヒグループHD":             "2502.T",
    "キリンHD":                     "2503.T",
    "サントリー食品":               "2587.T",
    "明治HD":                       "2202.T",
    "ヤクルト本社":                 "2267.T",
    "伊藤忠商事":                   "8001.T",
    "丸紅":                         "8002.T",
    "三井物産":                     "8031.T",
    "住友商事":                     "8053.T",
    "三菱商事":                     "8058.T",
    "豊田通商":                     "8015.T",
    "JAL":                          "9201.T",
    "ANAホールディングス":          "9202.T",
    "商船三井":                     "9104.T",
    "川崎汽船":                     "9107.T",
    "日本郵船":                     "9101.T",
    "ヤマトHD":                     "9064.T",
    "スクウェア・エニックス":       "9684.T",
    "カプコン":                     "9697.T",
    "任天堂":                       "7974.T",
    "コナミグループ":               "9766.T",
    "バンダイナムコHD":             "7832.T",
    "花王":                         "4452.T",
    "資生堂":                       "4911.T",
    "良品計画":                     "7453.T",
    "ニトリHD":                     "9843.T",
    "エムスリー":                   "2413.T",
    "リクルートHD":                 "6098.T",
    "日本郵政":                     "6178.T",
    "ベイカレント":                 "6532.T",
    "メルカリ":                     "4385.T",
    "SHIFT":                        "3697.T",
    "サイバーエージェント":         "4751.T",
    "ラクス":                       "3923.T",
    "freee":                        "4478.T",
    "マネーフォワード":             "3994.T",
    "トレンドマイクロ":             "4704.T",
    "野村総合研究所":               "4307.T",
    "三菱重工業":                   "7011.T",
    "IHI":                          "7013.T",
    "川崎重工業":                   "7012.T",
    "コマツ":                       "6301.T",
    "クボタ":                       "6326.T",
    "荏原製作所":                   "6361.T",
    "ミネベアミツミ":               "6479.T",
    "アルプスアルパイン":           "6770.T",
    "GSユアサ":                     "6674.T",
    "セイコーエプソン":             "6724.T",
    "コジマ":                       "2730.T",
    "ヨドバシカメラ":               "7950.T",
    "ビックカメラ":                 "3048.T",
    "ケーズホールディングス":       "8282.T",
    "ジョイフル本田":               "3191.T",
    "コーナン商事":                 "7516.T",
    "西松屋チェーン":               "7545.T",
    "しまむら":                     "8227.T",
    "ユニクロ（ファーストリテイリング）": "9983.T",
    "ワークマン":                   "7564.T",
    "MonotaRO":                     "3064.T",
    "GMOペイメントGW":              "3769.T",
    "デジタルアーツ":               "4819.T",
    "ラクスル":                     "4384.T",
    "弁護士ドットコム":             "6027.T",
    "Sansan":                       "4443.T",
    "スマートHR":                   "4443.T",
    "ウェルスナビ":                 "7342.T",
    "SBIホールディングス":          "8473.T",
    "楽天グループ":                 "4755.T",
    "DeNA":                         "2432.T",
    "グリー":                       "3632.T",
    "サイバーリンクス":             "3683.T",
    "オプティム":                   "3694.T",
    "CARTA HOLDINGS":               "3688.T",
    "ミクシィ":                     "2121.T",
    "ネクソン":                     "3659.T",
    "コロプラ":                     "3668.T",
    "Gungho":                       "3765.T",
    "東映アニメーション":           "4816.T",
    "エイベックス":                 "7860.T",
    "アミューズ":                   "4301.T",
    "吉本興業HD":                   "9465.T",
    "東宝":                         "9602.T",
    "松竹":                         "9601.T",
    "角川HD":                       "9468.T",
    "集英社":                       "不上場",
    "サイバーコネクトツー":         "不上場",
    "武蔵野銀行":                   "8336.T",
    "千葉銀行":                     "8331.T",
    "横浜銀行":                     "8332.T",
    "静岡銀行":                     "8355.T",
    "京都銀行":                     "8369.T",
    "南都銀行":                     "8367.T",
    "百十四銀行":                   "8386.T",
    "伊予銀行":                     "8385.T",
    "阿波銀行":                     "8388.T",
    "四国銀行":                     "8387.T",
}

# スクリーニング対象（上場銘柄のみ）
PRESET_TICKERS = {t: n for n, t in COMPANY_DICT.items() if t != "不上場"}


# ──────────────────────────────────────────────
# プリセットモード
# ──────────────────────────────────────────────
PRESET_MODES = {
    "🎯 株の買い時モード": {
        "description": "成長株の買いエントリーを狙う標準モード。トレンド・業績・流動性を総合判断。",
        "require_ma25_up":      True,
        "require_ma200_up":     True,
        "max_deviation_pct":    10.0,
        "require_bb":           True,
        "require_cup":          False,
        "min_revenue_growth":   10.0,
        "require_eps":          True,
        "min_volume":           50_000,
        "use_div_filter":       False,
        "min_div":              0.0,
        "max_div":              10.0,
        "min_score":            40,
    },
    "💰 配当利回り優先モード": {
        "description": "配当3%以上の銘柄を優先。長期保有・インカムゲイン狙いに最適。",
        "require_ma25_up":      True,
        "require_ma200_up":     False,
        "max_deviation_pct":    20.0,
        "require_bb":           False,
        "require_cup":          False,
        "min_revenue_growth":   0.0,
        "require_eps":          False,
        "min_volume":           30_000,
        "use_div_filter":       True,
        "min_div":              3.0,
        "max_div":              10.0,
        "min_score":            20,
    },
    "🚀 キャピタルゲインモード": {
        "description": "高成長・カップウィズハンドル検知で大幅上昇を狙う攻めのモード。",
        "require_ma25_up":      True,
        "require_ma200_up":     True,
        "max_deviation_pct":    15.0,
        "require_bb":           True,
        "require_cup":          True,
        "min_revenue_growth":   25.0,
        "require_eps":          True,
        "min_volume":           50_000,
        "use_div_filter":       False,
        "min_div":              0.0,
        "max_div":              10.0,
        "min_score":            60,
    },
    "⚙️ カスタム": {
        "description": "各条件を自分で細かく設定するモード。",
        "require_ma25_up":      True,
        "require_ma200_up":     True,
        "max_deviation_pct":    10.0,
        "require_bb":           True,
        "require_cup":          False,
        "min_revenue_growth":   10.0,
        "require_eps":          True,
        "min_volume":           50_000,
        "use_div_filter":       False,
        "min_div":              0.0,
        "max_div":              10.0,
        "min_score":            30,
    },
}


# ──────────────────────────────────────────────
# スクリーニング本体
# ──────────────────────────────────────────────

def _judge_single(df: pd.DataFrame, criteria: dict,
                  rev_growth: Optional[float],
                  eps_up: Optional[bool],
                  div_yield: float) -> tuple[Optional[int], str]:
    """指標計算とフィルタリングを行い (スコア, メッセージ) を返す。"""
    price   = df["Close"].iloc[-1]
    recent  = df.dropna(subset=["MA25","MA200"]).tail(5)
    if len(recent) < 2:
        return None, "MA算出不足"

    ma25_up  = recent["MA25"].iloc[-1]  > recent["MA25"].iloc[0]
    ma200_up = recent["MA200"].iloc[-1] > recent["MA200"].iloc[0]
    last_ma  = df.dropna(subset=["MA25"]).iloc[-1]
    deviation = (price - last_ma["MA25"]) / last_ma["MA25"] * 100

    last_bb = df.dropna(subset=["BB_upper3"]).iloc[-1]
    bb_ok   = price < last_bb["BB_upper3"]
    bw      = last_bb["BB_upper3"] - last_bb["BB_lower3"]
    bb_pos  = (price - last_bb["BB_lower3"]) / bw * 100 if bw > 0 else 50.0

    closes = df["Close"].dropna()
    cup = False
    cup_high = None
    if len(closes) >= 125:
        r125     = closes.tail(125)
        cup_high = r125.max()
        after    = r125[r125.index > r125.idxmax()]
        if len(after) >= 10:
            depth = (cup_high - after.min()) / cup_high * 100
            prox  = price / cup_high * 100
            cup   = (10 <= depth <= 40) and (prox >= 92)

    avg_vol = df["Volume"].tail(20).mean()

    # ── フィルタリング ──
    if criteria.get("require_ma25_up", True)  and not ma25_up:  return None, "MA25下向き"
    if criteria.get("require_ma200_up", True) and not ma200_up: return None, "MA200下向き"
    if abs(deviation) > criteria.get("max_deviation_pct", 10.0): return None, f"乖離率超過({deviation:+.1f}%)"
    if criteria.get("require_bb", True) and not bb_ok: return None, "BB+3σ超過"
    if criteria.get("require_cup", False) and not cup: return None, "カップ未検知"
    if rev_growth is not None and rev_growth < criteria.get("min_revenue_growth", 10.0):
        return None, f"売上成長率不足({rev_growth:+.1f}%)"
    if criteria.get("require_eps", True) and eps_up is False: return None, "EPS減少"
    if avg_vol < criteria.get("min_volume", 50_000): return None, f"出来高不足({avg_vol:,.0f}株)"
    if criteria.get("use_div_filter", False):
        if div_yield < criteria.get("min_div", 0) or div_yield > criteria.get("max_div", 10):
            return None, f"配当範囲外({div_yield:.2f}%)"

    # ── スコア ──
    score = 0
    if ma25_up:               score += 10
    if ma200_up:              score += 10
    if abs(deviation) <= 10:  score += 15
    if bb_ok:                 score += 10
    if cup:                   score += 15
    if rev_growth is not None:
        score += 15 if rev_growth >= 25 else (10 if rev_growth >= 10 else 0)
    else:
        score += 7
    if eps_up is True:        score += 15
    elif eps_up is None:      score += 7
    if avg_vol >= 50_000:     score += 10

    if score < criteria.get("min_score", 0): return None, f"スコア不足({score}点)"
    return score, "OK"


def screen_single(ticker: str, name: str, criteria: dict) -> dict:
    """1銘柄をスクリーニングする。"""
    base = {"ticker": ticker, "name": name, "pass": False, "error": ""}
    try:
        time.sleep(0.3 + random.uniform(0, 0.2))
        df_raw = fetch_price_history(ticker)
        if df_raw is None or len(df_raw) < 30:
            return {**base, "error": "データ取得失敗"}

        df    = calc_indicators(df_raw)
        price = df["Close"].iloc[-1]

        # 業績データ（stooqには財務データがないためスキップ扱い）
        rev_growth = None
        eps_up     = None
        div_yield  = 0.0

        score, msg = _judge_single(df, criteria, rev_growth, eps_up, div_yield)
        if score is None:
            return {**base, "error": msg}

        label = (
            "🟢 強い買い" if score >= 75 else
            "🟡 買い候補" if score >= 55 else
            "🟠 待ち"     if score >= 35 else
            "🔴 見送り"
        )

        avg_vol   = df_raw["Volume"].tail(20).mean()
        deviation = (price - df.dropna(subset=["MA25"]).iloc[-1]["MA25"]) \
                    / df.dropna(subset=["MA25"]).iloc[-1]["MA25"] * 100

        return {
            **base,
            "pass": True,
            "result": {
                "銘柄コード":   ticker.replace(".T",""),
                "銘柄名":       (name or ticker)[:18],
                "現在値":       f"¥{price:,.0f}",
                "スコア":       score,
                "判定":         label,
                "25日乖離率":   f"{deviation:+.1f}%",
                "配当利回り":   f"{div_yield:.2f}%",
                "カップ":       "✅" if False else "—",
                "_score_raw":   score,
                "_price":       price,
                "_avg_vol":     avg_vol,
            }
        }
    except Exception as e:
        return {**base, "error": str(e)[:40]}


def run_screener(ticker_dict: dict, criteria: dict,
                 progress_callback=None) -> tuple[pd.DataFrame, dict]:
    """並列スクリーニングを実行して (結果DataFrame, 統計) を返す。"""
    results = []
    stats   = {"total": len(ticker_dict), "fetched": 0, "passed": 0, "failed": 0}
    done    = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(screen_single, t, n, criteria): t
            for t, n in ticker_dict.items()
        }
        for future in as_completed(futures):
            done += 1
            try:
                r = future.result()
                if "データ取得失敗" in r.get("error",""):
                    stats["failed"] += 1
                else:
                    stats["fetched"] += 1
                if r.get("pass"):
                    stats["passed"] += 1
                    results.append(r["result"])
            except Exception:
                stats["failed"] += 1
            if progress_callback:
                progress_callback(done, stats["total"], stats["fetched"], stats["passed"])

    if not results:
        return pd.DataFrame(), stats

    df = (pd.DataFrame(results)
          .sort_values("_score_raw", ascending=False)
          .drop(columns=["_score_raw","_price","_avg_vol"])
          .reset_index(drop=True))
    df.index += 1
    return df, stats


def search_company(query: str) -> list[tuple[str, str]]:
    """
    会社名またはコードで検索する。
    Returns: [(ticker, name), ...]
    """
    q = query.strip().upper().replace(" ","")
    results = []
    for name, ticker in COMPANY_DICT.items():
        if ticker == "不上場":
            continue
        if (q in name.upper() or
            q in ticker.upper() or
            q in ticker.replace(".T","")):
            results.append((ticker, name))
    return results
