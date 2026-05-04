"""data_loader.py — yfinanceからのデータ取得処理"""

import yfinance as yf
import pandas as pd
from typing import Optional


def fetch_stock_data(ticker: str, period: str = "1y") -> Optional[pd.DataFrame]:
    """
    yfinanceから株価履歴データを取得する。

    Args:
        ticker: 銘柄コード（例: "6532.T"）
        period: 取得期間（デフォルト: 1年）

    Returns:
        株価履歴のDataFrame（取得失敗時はNone）
    """
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        # タイムゾーン情報を除去（Streamlitのplotで問題が出ないように）
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    except Exception as e:
        raise ValueError(f"株価データの取得に失敗しました: {e}")


def fetch_stock_info(ticker: str) -> dict:
    """
    銘柄の基本情報を取得する。

    Args:
        ticker: 銘柄コード

    Returns:
        銘柄情報の辞書
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            "name": info.get("longName") or info.get("shortName", ticker),
            "sector": info.get("sector", "不明"),
            "industry": info.get("industry", "不明"),
            "market_cap": info.get("marketCap"),
            "currency": info.get("currency", "JPY"),
        }
    except Exception:
        return {"name": ticker, "sector": "不明", "industry": "不明",
                "market_cap": None, "currency": "JPY"}


def fetch_quarterly_financials(ticker: str) -> dict:
    """
    四半期財務データ（売上高・EPS）を取得する。

    Args:
        ticker: 銘柄コード

    Returns:
        {
            "revenue": pd.Series（直近4四半期の売上高）,
            "eps": pd.Series（直近4四半期のEPS）,
            "avg_volume": float（直近20日の平均出来高）
        }
    """
    try:
        stock = yf.Ticker(ticker)

        # 四半期売上高
        q_financials = stock.quarterly_financials
        revenue = None
        if q_financials is not None and not q_financials.empty:
            if "Total Revenue" in q_financials.index:
                revenue = q_financials.loc["Total Revenue"].sort_index()

        # 四半期EPS
        q_earnings = stock.quarterly_earnings
        eps = None
        if q_earnings is not None and not q_earnings.empty:
            if "EPS" in q_earnings.columns:
                eps = q_earnings["EPS"].sort_index()

        # 直近20日の平均出来高
        hist = stock.history(period="1mo")
        avg_volume = hist["Volume"].mean() if not hist.empty else 0.0

        return {"revenue": revenue, "eps": eps, "avg_volume": avg_volume}
    except Exception as e:
        raise ValueError(f"財務データの取得に失敗しました: {e}")
