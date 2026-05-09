"""data_loader.py — stooqからの株価データ取得（yfinance不使用）"""

import requests
import pandas as pd
import numpy as np
import time
import random
from io import StringIO
from typing import Optional

# stooq CSV エンドポイント
STOOQ_URL = "https://stooq.com/q/d/l/?s={ticker}&i=d"
HEADERS   = {"User-Agent": "Mozilla/5.0 (compatible; InvestApp/1.0)"}


def _to_stooq_ticker(code: str) -> str:
    """7203.T → 7203.jp 形式に変換"""
    c = code.upper().replace(".T", "").replace(".JP", "").strip()
    return f"{c}.jp"


def fetch_price_history(ticker: str, retry: int = 2) -> Optional[pd.DataFrame]:
    """
    stooqから過去約1年の日足データを取得する。

    Returns:
        DataFrame(Open, High, Low, Close, Volume) or None
    """
    stooq_ticker = _to_stooq_ticker(ticker)
    url = STOOQ_URL.format(ticker=stooq_ticker)

    for attempt in range(retry + 1):
        try:
            time.sleep(0.3 + random.uniform(0, 0.3))
            resp = requests.get(url, headers=HEADERS, timeout=10)
            if resp.status_code != 200:
                time.sleep(1.0 * (attempt + 1))
                continue

            text = resp.text.strip()
            if not text or "No data" in text or len(text) < 50:
                return None

            df = pd.read_csv(StringIO(text))
            df.columns = [c.strip() for c in df.columns]

            # Date列を確認
            date_col = next((c for c in df.columns if "date" in c.lower()), None)
            if date_col is None:
                return None

            df[date_col] = pd.to_datetime(df[date_col])
            df = df.set_index(date_col).sort_index()

            # 必須列の確認
            required = {"Open","High","Low","Close","Volume"}
            if not required.issubset(set(df.columns)):
                # 列名が大文字小文字違いの場合に対応
                df.columns = [c.capitalize() for c in df.columns]
                if not required.issubset(set(df.columns)):
                    return None

            df = df[["Open","High","Low","Close","Volume"]].apply(pd.to_numeric, errors="coerce")
            df = df.dropna(subset=["Close"])

            # 直近1年分に絞る
            cutoff = pd.Timestamp.today() - pd.DateOffset(years=1)
            df = df[df.index >= cutoff]

            if len(df) < 30:
                return None

            return df

        except Exception:
            time.sleep(1.0 * (attempt + 1))

    return None


def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """テクニカル指標を計算して追加する"""
    df = df.copy()
    df["MA25"]      = df["Close"].rolling(25).mean()
    df["MA200"]     = df["Close"].rolling(200).mean()
    std             = df["Close"].rolling(25).std()
    df["BB_upper2"] = df["MA25"] + 2 * std
    df["BB_lower2"] = df["MA25"] - 2 * std
    df["BB_upper3"] = df["MA25"] + 3 * std
    df["BB_lower3"] = df["MA25"] - 3 * std
    return df
