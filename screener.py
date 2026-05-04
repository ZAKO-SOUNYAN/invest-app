"""screener.py — スクリーニングロジック（上位50銘柄 + 並列処理）"""

import yfinance as yf
import pandas as pd
from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from data_loader import fetch_stock_data, fetch_quarterly_financials
from logic import (
    calc_all_indicators, judge_ma_slope, judge_deviation,
    judge_bollinger, detect_cup_with_handle,
    judge_revenue_growth, judge_eps_trend, judge_volume,
)

# ──────────────────────────────────────────────
# 人気日本株 上位50銘柄プリセット
# ──────────────────────────────────────────────
PRESET_TICKERS = {
    "6532.T": "ベイカレント・コンサルティング",
    "4385.T": "メルカリ",
    "3697.T": "SHIFT",
    "9984.T": "ソフトバンクグループ",
    "4751.T": "サイバーエージェント",
    "6758.T": "ソニーグループ",
    "6861.T": "キーエンス",
    "6954.T": "ファナック",
    "7203.T": "トヨタ自動車",
    "6902.T": "デンソー",
    "6367.T": "ダイキン工業",
    "6971.T": "京セラ",
    "6501.T": "日立製作所",
    "6752.T": "パナソニックHD",
    "7735.T": "スクリーンHD",
    "6857.T": "アドバンテスト",
    "8035.T": "東京エレクトロン",
    "6723.T": "ルネサスエレクトロニクス",
    "4063.T": "信越化学工業",
    "6594.T": "ニデック",
    "8306.T": "三菱UFJフィナンシャルG",
    "8316.T": "三井住友フィナンシャルG",
    "8411.T": "みずほフィナンシャルG",
    "8604.T": "野村ホールディングス",
    "8725.T": "MS&ADインシュアランスG",
    "9983.T": "ファーストリテイリング",
    "3382.T": "セブン&アイ・ホールディングス",
    "8267.T": "イオン",
    "2802.T": "味の素",
    "2914.T": "日本たばこ産業（JT）",
    "4519.T": "中外製薬",
    "4568.T": "第一三共",
    "4502.T": "武田薬品工業",
    "6869.T": "シスメックス",
    "4543.T": "テルモ",
    "9432.T": "日本電信電話（NTT）",
    "9433.T": "KDDI",
    "9434.T": "ソフトバンク",
    "9020.T": "東日本旅客鉄道（JR東日本）",
    "9022.T": "東海旅客鉄道（JR東海）",
    "8801.T": "三井不動産",
    "8802.T": "三菱地所",
    "1925.T": "大和ハウス工業",
    "1928.T": "積水ハウス",
    "3288.T": "オープンハウスグループ",
    "7267.T": "本田技研工業（ホンダ）",
    "7741.T": "HOYA",
    "4901.T": "富士フイルムHD",
    "2413.T": "エムスリー",
    "6146.T": "ディスコ",
}

MAX_WORKERS = 8  # 並列スレッド数


@dataclass
class ScreenerCriteria:
    """スクリーニング基準（ユーザーが設定可能）"""
    require_ma25_up: bool = True
    require_ma200_up: bool = True
    max_deviation_pct: float = 10.0
    require_below_3sigma: bool = True
    require_cup_handle: bool = False
    min_revenue_growth_pct: float = 10.0
    require_eps_uptrend: bool = True
    min_volume: float = 50_000
    use_dividend_filter: bool = False
    min_dividend_yield: float = 0.0
    max_dividend_yield: float = 10.0
    min_score: int = 0


def fetch_dividend_yield(ticker: str) -> float:
    try:
        info = yf.Ticker(ticker).info
        dy = info.get("dividendYield")
        return round(dy * 100, 2) if dy else 0.0
    except Exception:
        return 0.0


def screen_single(ticker: str, name: str, criteria: ScreenerCriteria) -> Optional[dict]:
    """1銘柄をスクリーニングする。条件を満たさない場合はNoneを返す。"""
    try:
        df_raw = fetch_stock_data(ticker, period="1y")
        if df_raw is None or df_raw.empty:
            return None

        df  = calc_all_indicators(df_raw)
        ma  = judge_ma_slope(df)
        dev = judge_deviation(df)
        bb  = judge_bollinger(df)
        cup = detect_cup_with_handle(df)

        financials = fetch_quarterly_financials(ticker)
        rev = judge_revenue_growth(financials.get("revenue"))
        eps = judge_eps_trend(financials.get("eps"))
        vol = judge_volume(financials.get("avg_volume", 0))

        # フィルタリング
        if criteria.require_ma25_up and not ma["ma25_up"]:           return None
        if criteria.require_ma200_up and not ma["ma200_up"]:          return None
        if abs(dev["deviation_pct"]) > criteria.max_deviation_pct:    return None
        if criteria.require_below_3sigma and not bb["below_3sigma"]:  return None
        if criteria.require_cup_handle and not cup.get("detected"):   return None
        if (rev["growth_pct"] is not None and
                rev["growth_pct"] < criteria.min_revenue_growth_pct): return None
        if criteria.require_eps_uptrend and not eps["pass"]:          return None
        if vol["avg_volume"] < criteria.min_volume:                   return None

        # 配当利回り
        div_yield = fetch_dividend_yield(ticker)
        if criteria.use_dividend_filter:
            if div_yield < criteria.min_dividend_yield or div_yield > criteria.max_dividend_yield:
                return None

        # スコア計算
        score = 0
        if ma["ma25_up"]:       score += 10
        if ma["ma200_up"]:      score += 10
        if dev["within_10pct"]: score += 15
        if bb["below_3sigma"]:  score += 10
        if cup.get("detected"): score += 15 if cup.get("confidence") == "高" else 10
        if rev["pass"]:         score += 15 if (rev.get("growth_pct") or 0) >= 25 else 10
        if eps["pass"]:         score += 15
        if vol["pass"]:         score += 10

        if score < criteria.min_score:
            return None

        label = (
            "🟢 強い買い" if score >= 75 else
            "🟡 買い候補" if score >= 55 else
            "🟠 待ち"     if score >= 35 else
            "🔴 見送り"
        )

        latest = df["Close"].iloc[-1]

        return {
            "銘柄コード":   ticker.replace(".T", ""),
            "銘柄名":       name[:20],
            "現在値":       f"¥{latest:,.0f}",
            "スコア":       score,
            "判定":         label,
            "売上高成長率": f"{rev['growth_pct']:+.1f}%" if rev["growth_pct"] is not None else "N/A",
            "EPSトレンド":  eps["trend"],
            "25日乖離率":   f"{dev['deviation_pct']:+.1f}%",
            "配当利回り":   f"{div_yield:.2f}%",
            "カップ":       "✅" if cup.get("detected") else "—",
            "_score_raw":   score,
        }
    except Exception:
        return None


def run_screener(
    ticker_dict: dict,
    criteria: ScreenerCriteria,
    progress_callback=None,
) -> pd.DataFrame:
    """
    複数銘柄を並列スクリーニングしてDataFrameで返す。

    Args:
        ticker_dict: {"6532.T": "ベイカレント", ...}
        criteria: スクリーニング基準
        progress_callback: (done, total, ticker) を受け取るコールバック
    """
    results = []
    total   = len(ticker_dict)
    done    = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(screen_single, ticker, name, criteria): ticker
            for ticker, name in ticker_dict.items()
        }
        for future in as_completed(futures):
            ticker = futures[future]
            done  += 1
            if progress_callback:
                progress_callback(done, total, ticker)
            result = future.result()
            if result:
                results.append(result)

    if not results:
        return pd.DataFrame()

    df = (pd.DataFrame(results)
          .sort_values("_score_raw", ascending=False)
          .drop(columns=["_score_raw"])
          .reset_index(drop=True))
    df.index += 1
    return df
