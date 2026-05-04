"""logic.py — 指標計算と判定アルゴリズム"""

import pandas as pd
import numpy as np
from typing import Optional


# ──────────────────────────────────────────────
# テクニカル指標の計算
# ──────────────────────────────────────────────

def calc_moving_averages(df: pd.DataFrame) -> pd.DataFrame:
    """25日・200日移動平均線を計算してDataFrameに追加する。"""
    df = df.copy()
    df["MA25"] = df["Close"].rolling(window=25).mean()
    df["MA200"] = df["Close"].rolling(window=200).mean()
    return df


def calc_bollinger_bands(df: pd.DataFrame, window: int = 25) -> pd.DataFrame:
    """ボリンジャーバンド（±2σ・±3σ）を計算してDataFrameに追加する。"""
    df = df.copy()
    mid = df["Close"].rolling(window=window).mean()
    std = df["Close"].rolling(window=window).std()
    df["BB_mid"] = mid
    df["BB_upper2"] = mid + 2 * std
    df["BB_lower2"] = mid - 2 * std
    df["BB_upper3"] = mid + 3 * std
    df["BB_lower3"] = mid - 3 * std
    return df


def calc_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """全テクニカル指標をまとめて計算する。"""
    df = calc_moving_averages(df)
    df = calc_bollinger_bands(df)
    return df


# ──────────────────────────────────────────────
# テクニカル判定
# ──────────────────────────────────────────────

def judge_ma_slope(df: pd.DataFrame, window: int = 5) -> dict:
    """
    移動平均線の傾きを判定する。

    Returns:
        {"ma25_up": bool, "ma200_up": bool}
    """
    recent = df.dropna(subset=["MA25", "MA200"]).tail(window)
    if len(recent) < 2:
        return {"ma25_up": False, "ma200_up": False}

    ma25_slope = recent["MA25"].iloc[-1] - recent["MA25"].iloc[0]
    ma200_slope = recent["MA200"].iloc[-1] - recent["MA200"].iloc[0]

    return {
        "ma25_up": ma25_slope > 0,
        "ma200_up": ma200_slope > 0,
    }


def judge_deviation(df: pd.DataFrame) -> dict:
    """
    25日線乖離率を判定する。

    Returns:
        {"deviation_pct": float, "within_10pct": bool}
    """
    latest = df.dropna(subset=["MA25"]).iloc[-1]
    deviation = (latest["Close"] - latest["MA25"]) / latest["MA25"] * 100
    return {
        "deviation_pct": round(deviation, 2),
        "within_10pct": abs(deviation) <= 10.0,
    }


def judge_bollinger(df: pd.DataFrame) -> dict:
    """
    ボリンジャーバンドの判定（+3σに達していないか）。

    Returns:
        {"below_3sigma": bool, "bb_position_pct": float}
    """
    latest = df.dropna(subset=["BB_upper3", "BB_lower3", "BB_mid"]).iloc[-1]
    price = latest["Close"]
    upper3 = latest["BB_upper3"]
    lower3 = latest["BB_lower3"]

    # バンド内の相対位置（0%=下限, 100%=上限）
    band_width = upper3 - lower3
    position_pct = (price - lower3) / band_width * 100 if band_width > 0 else 50.0

    return {
        "below_3sigma": price < upper3,
        "bb_position_pct": round(position_pct, 1),
    }


# ──────────────────────────────────────────────
# カップウィズハンドル検知
# ──────────────────────────────────────────────

def detect_cup_with_handle(df: pd.DataFrame) -> dict:
    """
    簡易的なカップウィズハンドルパターンを検知する。

    ロジック概要:
      - 過去3〜6ヶ月（約60〜125営業日）の高値からの調整を検出
      - 直近の株価が調整前の高値水準に接近しているかを判定

    Returns:
        {"detected": bool, "confidence": str, "description": str}
    """
    closes = df["Close"].dropna()
    if len(closes) < 125:
        return {
            "detected": False,
            "confidence": "データ不足",
            "description": "200日分のデータが必要です。",
        }

    # 直近125日（約6ヶ月）の分析
    recent_125 = closes.tail(125)
    # カップの高値（直近125日の最高値）
    cup_high = recent_125.max()
    cup_high_idx = recent_125.idxmax()

    # 高値から現在までのデータ
    after_high = recent_125[recent_125.index > cup_high_idx]
    if len(after_high) < 10:
        return {
            "detected": False,
            "confidence": "低",
            "description": "高値圏からの調整期間が短すぎます。",
        }

    # カップの底（高値後の最安値）
    cup_low = after_high.min()
    cup_depth_pct = (cup_high - cup_low) / cup_high * 100

    current_price = closes.iloc[-1]
    # 高値への接近度（95%以上で高値ブレイク候補）
    proximity_pct = current_price / cup_high * 100

    # 判定条件
    # 調整幅: 10%〜40%（典型的なカップの深さ）
    depth_ok = 10 <= cup_depth_pct <= 40
    # 現在値が高値の92%以上（ハンドル形成〜ブレイク候補）
    near_high = proximity_pct >= 92

    detected = depth_ok and near_high
    confidence = "高" if (depth_ok and proximity_pct >= 97) else "中" if detected else "低"

    description = (
        f"カップ高値: ¥{cup_high:,.0f} | "
        f"調整幅: {cup_depth_pct:.1f}% | "
        f"現在値/高値: {proximity_pct:.1f}%"
    )

    return {
        "detected": detected,
        "confidence": confidence,
        "description": description,
        "cup_high": cup_high,
        "cup_low": cup_low,
        "proximity_pct": round(proximity_pct, 1),
    }


# ──────────────────────────────────────────────
# 業績判定
# ──────────────────────────────────────────────

def judge_revenue_growth(revenue: Optional[pd.Series]) -> dict:
    """
    売上高の前年同期比成長率を判定する。

    Returns:
        {"growth_pct": float|None, "pass": bool, "label": str}
    """
    if revenue is None or len(revenue) < 5:
        return {"growth_pct": None, "pass": False, "label": "データなし"}

    # 最新四半期 vs 1年前の同四半期
    latest = revenue.iloc[-1]
    year_ago = revenue.iloc[-5] if len(revenue) >= 5 else None

    if year_ago is None or year_ago == 0:
        return {"growth_pct": None, "pass": False, "label": "比較不可"}

    growth = (latest - year_ago) / abs(year_ago) * 100
    passed = growth >= 10.0
    label = "◎ 25%以上増収" if growth >= 25 else "○ 10%以上増収" if passed else "× 基準未達"

    return {"growth_pct": round(growth, 1), "pass": passed, "label": label}


def judge_eps_trend(eps: Optional[pd.Series]) -> dict:
    """
    EPSの増加基調を判定する（直近3四半期が連続増加）。

    Returns:
        {"trend": str, "pass": bool}
    """
    if eps is None or len(eps) < 3:
        return {"trend": "データなし", "pass": False}

    recent = eps.dropna().tail(4)
    if len(recent) < 3:
        return {"trend": "データ不足", "pass": False}

    # 連続増加チェック
    diffs = recent.diff().dropna()
    increasing = (diffs > 0).sum()
    total = len(diffs)

    if increasing == total:
        trend = "◎ 連続増加"
        passed = True
    elif increasing >= total * 0.5:
        trend = "△ 増加基調"
        passed = True
    else:
        trend = "× 減少傾向"
        passed = False

    return {"trend": trend, "pass": passed}


def judge_volume(avg_volume: float) -> dict:
    """出来高が5万株以上かを判定する。"""
    passed = avg_volume >= 50_000
    return {
        "avg_volume": avg_volume,
        "pass": passed,
        "label": f"{'○' if passed else '×'} {avg_volume:,.0f}株/日（平均）",
    }


# ──────────────────────────────────────────────
# 総合投資スコア
# ──────────────────────────────────────────────

def calc_investment_score(
    ma_result: dict,
    deviation_result: dict,
    bb_result: dict,
    cup_result: dict,
    revenue_result: dict,
    eps_result: dict,
    volume_result: dict,
) -> dict:
    """
    各判定結果から100点満点の投資スコアを算出する。

    配点:
      テクニカル (60点):
        MA25上向き        10点
        MA200上向き       10点
        25日乖離率10%以内  15点
        BB+3σ未達         10点
        カップウィズハンドル 15点
      業績 (40点):
        売上高成長率       15点
        EPS増加基調        15点
        出来高5万株以上    10点
    """
    score = 0
    breakdown = {}

    # MA25
    if ma_result.get("ma25_up"):
        score += 10
        breakdown["MA25上向き"] = 10
    else:
        breakdown["MA25上向き"] = 0

    # MA200
    if ma_result.get("ma200_up"):
        score += 10
        breakdown["MA200上向き"] = 10
    else:
        breakdown["MA200上向き"] = 0

    # 乖離率
    if deviation_result.get("within_10pct"):
        score += 15
        breakdown["25日乖離率10%以内"] = 15
    else:
        breakdown["25日乖離率10%以内"] = 0

    # ボリンジャー
    if bb_result.get("below_3sigma"):
        score += 10
        breakdown["BB+3σ未達"] = 10
    else:
        breakdown["BB+3σ未達"] = 0

    # カップウィズハンドル
    if cup_result.get("detected"):
        pts = 15 if cup_result.get("confidence") == "高" else 10
        score += pts
        breakdown["カップウィズハンドル"] = pts
    else:
        breakdown["カップウィズハンドル"] = 0

    # 売上高成長率
    if revenue_result.get("pass"):
        growth = revenue_result.get("growth_pct") or 0
        pts = 15 if growth >= 25 else 10
        score += pts
        breakdown["売上高成長率"] = pts
    else:
        breakdown["売上高成長率"] = 0

    # EPS
    if eps_result.get("pass"):
        score += 15
        breakdown["EPS増加基調"] = 15
    else:
        breakdown["EPS増加基調"] = 0

    # 出来高
    if volume_result.get("pass"):
        score += 10
        breakdown["出来高5万株以上"] = 10
    else:
        breakdown["出来高5万株以上"] = 0

    # 判定ラベル
    if score >= 75:
        label = "🟢 強い買いシグナル"
    elif score >= 55:
        label = "🟡 買い候補（要確認）"
    elif score >= 35:
        label = "🟠 待ち"
    else:
        label = "🔴 見送り"

    return {"score": score, "label": label, "breakdown": breakdown}
