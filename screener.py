"""screener.py — スクリーニングロジック（レート制限対策・リトライ付き）"""

import yfinance as yf
import pandas as pd
import time
import random
from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# レート制限対策：並列数を抑える
MAX_WORKERS = 2
RETRY_COUNT = 2          # 失敗時のリトライ回数
RETRY_DELAY = 2.0        # リトライ間の待機秒数
REQUEST_DELAY = 0.5      # 1リクエストごとの間隔（秒）

# ──────────────────────────────────────────────
# 日本株 上位300銘柄プリセット
# ──────────────────────────────────────────────
PRESET_TICKERS = {
    "6758.T": "ソニーグループ",
    "6861.T": "キーエンス",
    "7203.T": "トヨタ自動車",
    "9984.T": "ソフトバンクグループ",
    "8035.T": "東京エレクトロン",
    "6954.T": "ファナック",
    "6902.T": "デンソー",
    "6367.T": "ダイキン工業",
    "6971.T": "京セラ",
    "6501.T": "日立製作所",
    "6857.T": "アドバンテスト",
    "6723.T": "ルネサスエレクトロニクス",
    "4063.T": "信越化学工業",
    "6594.T": "ニデック",
    "7735.T": "スクリーンHD",
    "6752.T": "パナソニックHD",
    "6701.T": "NEC",
    "6702.T": "富士通",
    "6645.T": "オムロン",
    "6976.T": "太陽誘電",
    "6981.T": "村田製作所",
    "6963.T": "ローム",
    "4062.T": "イビデン",
    "6146.T": "ディスコ",
    "7741.T": "HOYA",
    "4901.T": "富士フイルムHD",
    "7751.T": "キヤノン",
    "7733.T": "オリンパス",
    "7731.T": "ニコン",
    "6724.T": "セイコーエプソン",
    "9432.T": "NTT",
    "9433.T": "KDDI",
    "9434.T": "ソフトバンク",
    "9020.T": "JR東日本",
    "9022.T": "JR東海",
    "9021.T": "JR西日本",
    "9142.T": "JR九州",
    "9501.T": "東京電力HD",
    "9502.T": "中部電力",
    "9503.T": "関西電力",
    "9531.T": "東京ガス",
    "9532.T": "大阪ガス",
    "8306.T": "三菱UFJ FG",
    "8316.T": "三井住友FG",
    "8411.T": "みずほFG",
    "8604.T": "野村HD",
    "8725.T": "MS&AD",
    "8750.T": "第一生命HD",
    "8766.T": "東京海上HD",
    "8630.T": "SOMPOホールディングス",
    "8601.T": "大和証券G本社",
    "8697.T": "日本取引所G",
    "9983.T": "ファーストリテイリング",
    "3382.T": "セブン&アイHD",
    "8267.T": "イオン",
    "2802.T": "味の素",
    "2914.T": "JT",
    "3086.T": "Jフロントリテイリング",
    "3099.T": "三越伊勢丹HD",
    "3092.T": "ZOZO",
    "2651.T": "ローソン",
    "2670.T": "ABCマート",
    "2695.T": "くら寿司",
    "2702.T": "マクドナルドHD",
    "4519.T": "中外製薬",
    "4568.T": "第一三共",
    "4502.T": "武田薬品工業",
    "6869.T": "シスメックス",
    "4543.T": "テルモ",
    "4507.T": "塩野義製薬",
    "4523.T": "エーザイ",
    "4530.T": "久光製薬",
    "4536.T": "参天製薬",
    "4540.T": "ツムラ",
    "4544.T": "HUグループHD",
    "8801.T": "三井不動産",
    "8802.T": "三菱地所",
    "1925.T": "大和ハウス工業",
    "1928.T": "積水ハウス",
    "3288.T": "オープンハウスG",
    "3289.T": "東急不動産HD",
    "8804.T": "東京建物",
    "8830.T": "住友不動産",
    "3231.T": "野村不動産HD",
    "3003.T": "ヒューリック",
    "7267.T": "ホンダ",
    "7261.T": "マツダ",
    "7269.T": "スズキ",
    "7270.T": "SUBARU",
    "7272.T": "ヤマハ発動機",
    "7201.T": "日産自動車",
    "7202.T": "いすゞ自動車",
    "4188.T": "三菱ケミカルG",
    "4183.T": "三井化学",
    "4005.T": "住友化学",
    "4021.T": "日産化学",
    "4042.T": "東ソー",
    "4061.T": "デンカ",
    "4088.T": "エア・ウォーター",
    "5019.T": "出光興産",
    "5020.T": "ENEOSホールディングス",
    "5108.T": "ブリヂストン",
    "5105.T": "TOYO TIRE",
    "5101.T": "横浜ゴム",
    "1801.T": "大成建設",
    "1802.T": "大林組",
    "1803.T": "清水建設",
    "1812.T": "鹿島建設",
    "1820.T": "西松建設",
    "1824.T": "前田建設工業",
    "2501.T": "サッポロHD",
    "2502.T": "アサヒグループHD",
    "2503.T": "キリンHD",
    "2587.T": "サントリー食品",
    "2201.T": "森永製菓",
    "2202.T": "明治HD",
    "2264.T": "森永乳業",
    "2267.T": "ヤクルト本社",
    "8001.T": "伊藤忠商事",
    "8002.T": "丸紅",
    "8031.T": "三井物産",
    "8053.T": "住友商事",
    "8058.T": "三菱商事",
    "8015.T": "豊田通商",
    "9201.T": "JAL",
    "9202.T": "ANAホールディングス",
    "9104.T": "商船三井",
    "9107.T": "川崎汽船",
    "9101.T": "日本郵船",
    "9064.T": "ヤマトHD",
    "9684.T": "スクウェア・エニックス",
    "9697.T": "カプコン",
    "7974.T": "任天堂",
    "9766.T": "コナミグループ",
    "7832.T": "バンダイナムコHD",
    "4452.T": "花王",
    "4911.T": "資生堂",
    "4927.T": "ポーラ・オルビスHD",
    "7453.T": "良品計画",
    "9843.T": "ニトリHD",
    "2413.T": "エムスリー",
    "6098.T": "リクルートHD",
    "6178.T": "日本郵政",
    "6532.T": "ベイカレント",
    "4385.T": "メルカリ",
    "3697.T": "SHIFT",
    "4751.T": "サイバーエージェント",
    "2432.T": "DeNA",
    "3923.T": "ラクス",
    "4478.T": "freee",
    "4480.T": "メドレー",
    "3994.T": "マネーフォワード",
    "4704.T": "トレンドマイクロ",
    "4307.T": "野村総合研究所",
    "7011.T": "三菱重工業",
    "7013.T": "IHI",
    "7012.T": "川崎重工業",
    "6301.T": "コマツ",
    "6326.T": "クボタ",
    "6361.T": "荏原製作所",
    "6770.T": "アルプスアルパイン",
    "6479.T": "ミネベアミツミ",
    "6674.T": "GSユアサ",
    "6703.T": "沖電気工業",
    "7956.T": "ピジョン",
    "8334.T": "群馬銀行",
    "8354.T": "ふくおかFG",
    "8359.T": "八十二銀行",
    "8366.T": "滋賀銀行",
    "3197.T": "すかいらーくHD",
    "2726.T": "パルグループHD",
    "4506.T": "住友ファーマ",
    "4516.T": "日本新薬",
    "4508.T": "田辺三菱製薬",
    "4547.T": "キッセイ薬品工業",
    "4549.T": "栄研化学",
    "3291.T": "飯田グループHD",
    "8905.T": "イオンモール",
    "7205.T": "日野自動車",
    "7211.T": "三菱自動車工業",
    "4182.T": "三菱ガス化学",
    "4043.T": "トクヤマ",
    "4064.T": "チッソ",
    "9065.T": "山九",
    "9069.T": "センコーグループHD",
    "2121.T": "ミクシィ",
    "3659.T": "ネクソン",
    "3765.T": "ガンホー・オンライン",
    "2768.T": "双日",
    "6819.T": "伊豆シャボテンリゾート",
    "7186.T": "コンコルディアFG",
    "8338.T": "常陽銀行",
    "8341.T": "七十七銀行",
    "8361.T": "大垣共立銀行",
    "8362.T": "福井銀行",
    "3093.T": "トレジャーファクトリー",
    "2729.T": "JALUX",
    "2753.T": "あみやき亭",
    "4819.T": "デジタルアーツ",
    "3769.T": "GMOペイメントGW",
    "4384.T": "ラクスル",
    "4436.T": "ミンカブ",
    "4448.T": "Chatwork",
    "4493.T": "サイバーセキュリティクラウド",
    "4170.T": "Kaizen Platform",
    "6588.T": "東芝テック",
    "7762.T": "シチズン時計",
    "9508.T": "九州電力",
    "9509.T": "北海道電力",
    "9513.T": "電源開発",
    "8795.T": "T&Dホールディングス",
    "1821.T": "三井住友建設",
    "1833.T": "奥村組",
    "2220.T": "亀田製菓",
    "9068.T": "丸全昭和運輸",
    "9070.T": "トナミHD",
    "4550.T": "日水製薬",
    "4551.T": "鳥居薬品",
    "3249.T": "産業ファンド投資法人",
    "8848.T": "レオパレス21",
    "4491.T": "コンピュータマインド",
    "4371.T": "コアコンセプトT",
    "4565.T": "そーせいグループ",
    "2764.T": "ひらまつ",
    "4380.T": "Mマート",
    "4374.T": "Laboro.AI",
    "6302.T": "住友重機械工業",
    "6305.T": "日立建機",
    "6753.T": "シャープ",
    "4482.T": "ウィルズ",
    "4483.T": "JMDC",
    "4487.T": "スペースマーケット",
    "4488.T": "AIinside",
    "4489.T": "パーソルHD",
    "4490.T": "ピアズ",
    "3680.T": "ホットリンク",
    "3681.T": "ブロードリーフ",
    "3682.T": "エコモット",
    "3683.T": "サイバーリンクス",
    "3686.T": "DLE",
    "3688.T": "CARTA HOLDINGS",
    "3689.T": "イグニス",
    "3690.T": "イルグルム",
    "3691.T": "デジタルプラス",
    "3692.T": "FFRIセキュリティ",
    "3693.T": "CINC",
    "3694.T": "オプティム",
    "3696.T": "セレス",
    "3698.T": "CDS",
    "3699.T": "エアトリ",
    "6030.T": "アドベンチャー",
    "6031.T": "サイエンスアーツ",
    "6032.T": "インターワークス",
    "7048.T": "ベルトラ",
    "7049.T": "識学",
    "7050.T": "フォースタートアップス",
    "7051.T": "ハウテレビジョン",
    "7052.T": "ロードスターキャピタル",
    "7053.T": "LITALICO",
    "7054.T": "ポピンズHD",
    "7055.T": "ピースデジタル",
    "7056.T": "Waris",
    "7058.T": "共栄セキュリティー",
    "7059.T": "コプロHD",
    "7060.T": "ギークス",
}


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


# ──────────────────────────────────────────────
# データ取得（リトライ付き）
# ──────────────────────────────────────────────

def _fetch_history_with_retry(ticker: str) -> Optional[pd.DataFrame]:
    """株価履歴をリトライ付きで取得する。"""
    for attempt in range(RETRY_COUNT + 1):
        try:
            time.sleep(REQUEST_DELAY + random.uniform(0, 0.5))
            df = yf.Ticker(ticker).history(period="1y")
            if df is not None and not df.empty:
                df.index = pd.to_datetime(df.index)
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                return df
        except Exception:
            if attempt < RETRY_COUNT:
                time.sleep(RETRY_DELAY * (attempt + 1))
    return None


def _calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA25"]  = df["Close"].rolling(25).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    std = df["Close"].rolling(25).std()
    df["BB_upper2"] = df["MA25"] + 2 * std
    df["BB_lower2"] = df["MA25"] - 2 * std
    df["BB_upper3"] = df["MA25"] + 3 * std
    df["BB_lower3"] = df["MA25"] - 3 * std
    return df


def _get_revenue_growth(ticker: str) -> Optional[float]:
    try:
        time.sleep(REQUEST_DELAY)
        qf = yf.Ticker(ticker).quarterly_financials
        if qf is None or qf.empty:
            return None
        for key in ["Total Revenue", "Revenue", "Revenues"]:
            if key in qf.index:
                rev = qf.loc[key].dropna().sort_index()
                if len(rev) >= 5:
                    return round((rev.iloc[-1] - rev.iloc[-5]) / abs(rev.iloc[-5]) * 100, 1)
        return None
    except Exception:
        return None


def _get_eps_uptrend(ticker: str) -> Optional[bool]:
    try:
        time.sleep(REQUEST_DELAY)
        qe = yf.Ticker(ticker).quarterly_earnings
        if qe is None or qe.empty or "EPS" not in qe.columns:
            return None
        eps = qe["EPS"].dropna().tail(4)
        if len(eps) < 3:
            return None
        diffs = eps.diff().dropna()
        return (diffs > 0).sum() >= len(diffs) * 0.5
    except Exception:
        return None


def _get_dividend_yield(ticker: str) -> float:
    try:
        dy = yf.Ticker(ticker).info.get("dividendYield")
        return round(dy * 100, 2) if dy else 0.0
    except Exception:
        return 0.0


# ──────────────────────────────────────────────
# 1銘柄スクリーニング
# ──────────────────────────────────────────────

def screen_single(ticker: str, name: str, criteria: ScreenerCriteria) -> dict:
    """
    1銘柄をスクリーニングする。
    Returns: result dict（pass=Trueが条件合格、pass=Falseは不合格）
    """
    base = {"ticker": ticker, "name": name, "pass": False, "error": None}

    try:
        df_raw = _fetch_history_with_retry(ticker)
        if df_raw is None or len(df_raw) < 30:
            base["error"] = "データ取得失敗"
            return base

        df    = _calc_indicators(df_raw)
        price = df["Close"].iloc[-1]

        # ── テクニカル計算 ──
        recent   = df.dropna(subset=["MA25", "MA200"]).tail(5)
        if len(recent) < 2:
            base["error"] = "MA算出不足"
            return base

        ma25_up  = recent["MA25"].iloc[-1]  > recent["MA25"].iloc[0]
        ma200_up = recent["MA200"].iloc[-1] > recent["MA200"].iloc[0]
        last_ma  = df.dropna(subset=["MA25"]).iloc[-1]
        deviation = (price - last_ma["MA25"]) / last_ma["MA25"] * 100

        bb_ok  = True
        bb_pos = 50.0
        if "BB_upper3" in df.columns:
            last_bb = df.dropna(subset=["BB_upper3"]).iloc[-1]
            bb_ok   = price < last_bb["BB_upper3"]
            bw      = last_bb["BB_upper3"] - last_bb["BB_lower3"]
            bb_pos  = (price - last_bb["BB_lower3"]) / bw * 100 if bw > 0 else 50.0

        closes = df["Close"].dropna()
        cup_detected = False
        cup_high_val = None
        if len(closes) >= 125:
            r125 = closes.tail(125)
            cup_high_val = r125.max()
            after = r125[r125.index > r125.idxmax()]
            if len(after) >= 10:
                depth = (cup_high_val - after.min()) / cup_high_val * 100
                prox  = price / cup_high_val * 100
                cup_detected = (10 <= depth <= 40) and (prox >= 92)

        avg_vol = df_raw["Volume"].tail(20).mean()

        # ── 業績データ ──
        rev_growth  = _get_revenue_growth(ticker)
        eps_uptrend = _get_eps_uptrend(ticker)
        div_yield   = _get_dividend_yield(ticker)

        # ── フィルタリング（Falseを返すと不合格） ──
        if criteria.require_ma25_up  and not ma25_up:  return {**base, "error": "MA25下向き"}
        if criteria.require_ma200_up and not ma200_up: return {**base, "error": "MA200下向き"}
        if abs(deviation) > criteria.max_deviation_pct:
            return {**base, "error": f"乖離率超過({deviation:+.1f}%)"}
        if criteria.require_below_3sigma and not bb_ok:
            return {**base, "error": "BB+3σ超過"}
        if criteria.require_cup_handle and not cup_detected:
            return {**base, "error": "カップ未検知"}
        if rev_growth is not None and rev_growth < criteria.min_revenue_growth_pct:
            return {**base, "error": f"成長率不足({rev_growth:+.1f}%)"}
        if eps_uptrend is not None and criteria.require_eps_uptrend and not eps_uptrend:
            return {**base, "error": "EPS減少傾向"}
        if avg_vol < criteria.min_volume:
            return {**base, "error": f"出来高不足({avg_vol:,.0f}株)"}
        if criteria.use_dividend_filter:
            if div_yield < criteria.min_dividend_yield or div_yield > criteria.max_dividend_yield:
                return {**base, "error": f"配当利回り範囲外({div_yield:.2f}%)"}

        # ── スコア計算 ──
        score = 0
        if ma25_up:               score += 10
        if ma200_up:              score += 10
        if abs(deviation) <= 10:  score += 15
        if bb_ok:                 score += 10
        if cup_detected:          score += 15
        if rev_growth is not None:
            score += 15 if rev_growth >= 25 else (10 if rev_growth >= 10 else 0)
        else:
            score += 7  # データなし→部分点
        if eps_uptrend is True:   score += 15
        elif eps_uptrend is None: score += 7  # データなし→部分点
        if avg_vol >= 50_000:     score += 10

        if score < criteria.min_score:
            return {**base, "error": f"スコア不足({score}点)"}

        label = (
            "🟢 強い買い" if score >= 75 else
            "🟡 買い候補" if score >= 55 else
            "🟠 待ち"     if score >= 35 else
            "🔴 見送り"
        )

        return {
            "ticker": ticker,
            "name":   name,
            "pass":   True,
            "error":  None,
            "result": {
                "銘柄コード":   ticker.replace(".T", ""),
                "銘柄名":       (name or ticker)[:18],
                "現在値":       f"¥{price:,.0f}",
                "スコア":       score,
                "判定":         label,
                "売上高成長率": f"{rev_growth:+.1f}%" if rev_growth is not None else "取得不可",
                "EPS":          ("↑増加" if eps_uptrend else "↓減少") if eps_uptrend is not None else "取得不可",
                "25日乖離率":   f"{deviation:+.1f}%",
                "配当利回り":   f"{div_yield:.2f}%",
                "カップ":       "✅" if cup_detected else "—",
                "_score_raw":   score,
            }
        }

    except Exception as e:
        return {**base, "error": str(e)[:30]}


# ──────────────────────────────────────────────
# 並列スクリーナー実行
# ──────────────────────────────────────────────

def run_screener(
    ticker_dict: dict,
    criteria: ScreenerCriteria,
    progress_callback=None,
) -> tuple[pd.DataFrame, dict]:
    """
    Returns:
        (result_df, stats)
        stats = {"total": N, "fetched": N, "passed": N, "failed": N}
    """
    results  = []
    stats    = {"total": len(ticker_dict), "fetched": 0, "passed": 0, "failed": 0}
    done     = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(screen_single, ticker, name, criteria): ticker
            for ticker, name in ticker_dict.items()
        }
        for future in as_completed(futures):
            done += 1
            try:
                r = future.result()
                if r.get("error") != "データ取得失敗" and r.get("error") != "MA算出不足":
                    stats["fetched"] += 1
                else:
                    stats["failed"] += 1

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
          .drop(columns=["_score_raw"])
          .reset_index(drop=True))
    df.index += 1
    return df, stats
