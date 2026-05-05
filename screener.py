"""screener.py — スクリーニングロジック（上位300銘柄 + 並列処理）"""

import yfinance as yf
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_WORKERS = 6  # 並列スレッド数

# ──────────────────────────────────────────────
# 日本株 上位300銘柄プリセット
# ──────────────────────────────────────────────
PRESET_TICKERS = {
    # IT・ソフトウェア
    "6532.T": "ベイカレント",
    "4385.T": "メルカリ",
    "3697.T": "SHIFT",
    "4751.T": "サイバーエージェント",
    "2432.T": "DeNA",
    "4819.T": "デジタルアーツ",
    "4188.T": "三菱ケミカルG",
    "4369.T": "トリケミカル研究所",
    "3769.T": "GMOペイメントゲートウェイ",
    "4384.T": "ラクスル",
    "4382.T": "HEROZ",
    "4371.T": "コアコンセプトT",
    "4380.T": "Mマート",
    "4374.T": "Laboro.AI",
    "2413.T": "エムスリー",
    "4436.T": "ミンカブ",
    "4448.T": "Chatwork",
    "3923.T": "ラクス",
    "4478.T": "freee",
    "4480.T": "メドレー",
    "4491.T": "コンピュータマインド",
    "4493.T": "サイバーセキュリティクラウド",
    "3994.T": "マネーフォワード",
    "4565.T": "そーせいグループ",
    "4170.T": "Kaizen Platform",
    # 製造・電機
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
    "6301.T": "コマツ",
    "6326.T": "クボタ",
    "6302.T": "住友重機械工業",
    "6305.T": "日立建機",
    "7011.T": "三菱重工業",
    "7013.T": "IHI",
    "7012.T": "川崎重工業",
    "6361.T": "荏原製作所",
    "6363.T": "酉島製作所",
    "6370.T": "栗田工業",
    # 半導体・電子部品
    "6857.T": "アドバンテスト",
    "8035.T": "東京エレクトロン",
    "6723.T": "ルネサスエレクトロニクス",
    "4063.T": "信越化学工業",
    "6594.T": "ニデック",
    "6976.T": "太陽誘電",
    "6981.T": "村田製作所",
    "6770.T": "アルプスアルパイン",
    "6753.T": "シャープ",
    "6146.T": "ディスコ",
    "7741.T": "HOYA",
    "6963.T": "ローム",
    "6479.T": "ミネベアミツミ",
    "4062.T": "イビデン",
    "6588.T": "東芝テック",
    "6645.T": "オムロン",
    "6674.T": "GSユアサ",
    "6701.T": "NEC",
    "6702.T": "富士通",
    "6703.T": "沖電気工業",
    # 精密・光学
    "7762.T": "シチズン時計",
    "7733.T": "オリンパス",
    "7731.T": "ニコン",
    "7832.T": "バンダイナムコHD",
    "6146.T": "ディスコ",
    "4901.T": "富士フイルムHD",
    "7751.T": "キヤノン",
    "7752.T": "リコー",
    "6724.T": "セイコーエプソン",
    "7956.T": "ピジョン",
    # 通信・インフラ
    "9432.T": "NTT",
    "9433.T": "KDDI",
    "9434.T": "ソフトバンク",
    "9984.T": "ソフトバンクグループ",
    "9020.T": "JR東日本",
    "9022.T": "JR東海",
    "9021.T": "JR西日本",
    "9142.T": "JR九州",
    "9501.T": "東京電力HD",
    "9502.T": "中部電力",
    "9503.T": "関西電力",
    "9531.T": "東京ガス",
    "9532.T": "大阪ガス",
    "9508.T": "九州電力",
    "9509.T": "北海道電力",
    "9513.T": "電源開発",
    # 金融
    "8306.T": "三菱UFJ FG",
    "8316.T": "三井住友FG",
    "8411.T": "みずほFG",
    "8604.T": "野村HD",
    "8725.T": "MS&AD",
    "8750.T": "第一生命HD",
    "8766.T": "東京海上HD",
    "8795.T": "T&Dホールディングス",
    "8630.T": "SOMPOホールディングス",
    "8601.T": "大和証券G本社",
    "8697.T": "日本取引所G",
    "7186.T": "コンコルディアFG",
    "8334.T": "群馬銀行",
    "8338.T": "常陽銀行",
    "8341.T": "七十七銀行",
    "8354.T": "ふくおかFG",
    "8359.T": "八十二銀行",
    "8361.T": "大垣共立銀行",
    "8362.T": "福井銀行",
    "8366.T": "滋賀銀行",
    # 小売・消費財
    "9983.T": "ファーストリテイリング",
    "3382.T": "セブン&アイHD",
    "8267.T": "イオン",
    "2802.T": "味の素",
    "2914.T": "JT",
    "3086.T": "Jフロントリテイリング",
    "3099.T": "三越伊勢丹HD",
    "3092.T": "ZOZO",
    "3093.T": "トレジャーファクトリー",
    "3197.T": "すかいらーくHD",
    "2651.T": "ローソン",
    "8028.T": "ファミリーマート",
    "3382.T": "セブン&アイHD",
    "2670.T": "ABCマート",
    "2695.T": "くら寿司",
    "2702.T": "マクドナルドHD",
    "2726.T": "パルグループHD",
    "2729.T": "JALUX",
    "2753.T": "あみやき亭",
    "2764.T": "ひらまつ",
    # ヘルスケア・医薬
    "4519.T": "中外製薬",
    "4568.T": "第一三共",
    "4502.T": "武田薬品工業",
    "6869.T": "シスメックス",
    "4543.T": "テルモ",
    "4507.T": "塩野義製薬",
    "4523.T": "エーザイ",
    "4506.T": "大日本住友製薬",
    "4516.T": "日本新薬",
    "4508.T": "田辺三菱製薬",
    "4530.T": "久光製薬",
    "4536.T": "参天製薬",
    "4540.T": "ツムラ",
    "4541.T": "日医工",
    "4544.T": "HUグループHD",
    "4547.T": "キッセイ薬品工業",
    "4548.T": "生化学工業",
    "4549.T": "栄研化学",
    "4550.T": "日水製薬",
    "4551.T": "鳥居薬品",
    # 不動産
    "8801.T": "三井不動産",
    "8802.T": "三菱地所",
    "1925.T": "大和ハウス工業",
    "1928.T": "積水ハウス",
    "3288.T": "オープンハウスG",
    "3289.T": "東急不動産HD",
    "3291.T": "飯田グループHD",
    "8804.T": "東京建物",
    "8830.T": "住友不動産",
    "3231.T": "野村不動産HD",
    "8848.T": "レオパレス21",
    "3003.T": "ヒューリック",
    "8905.T": "イオンモール",
    "3249.T": "産業ファンド投資法人",
    "3269.T": "アドバンス・レジデンス",
    # 自動車・輸送機器
    "7267.T": "ホンダ",
    "7261.T": "マツダ",
    "7269.T": "スズキ",
    "7270.T": "SUBARU",
    "7272.T": "ヤマハ発動機",
    "7201.T": "日産自動車",
    "7202.T": "いすゞ自動車",
    "7205.T": "日野自動車",
    "7211.T": "三菱自動車工業",
    "7213.T": "レシップHD",
    # 素材・化学
    "4188.T": "三菱ケミカルG",
    "4183.T": "三井化学",
    "4182.T": "三菱ガス化学",
    "4005.T": "住友化学",
    "4021.T": "日産化学",
    "4042.T": "東ソー",
    "4043.T": "トクヤマ",
    "4061.T": "デンカ",
    "4064.T": "チッソ",
    "4088.T": "エア・ウォーター",
    "5019.T": "出光興産",
    "5020.T": "ENEOSホールディングス",
    "5101.T": "横浜ゴム",
    "5105.T": "TOYO TIRE",
    "5108.T": "ブリヂストン",
    # 建設・土木
    "1801.T": "大成建設",
    "1802.T": "大林組",
    "1803.T": "清水建設",
    "1812.T": "鹿島建設",
    "1820.T": "西松建設",
    "1821.T": "三井住友建設",
    "1822.T": "大豊建設",
    "1824.T": "前田建設工業",
    "1826.T": "佐田建設",
    "1833.T": "奥村組",
    # 食品・飲料
    "2501.T": "サッポロHD",
    "2502.T": "アサヒグループHD",
    "2503.T": "キリンHD",
    "2587.T": "サントリー食品インターナショナル",
    "2201.T": "森永製菓",
    "2202.T": "明治HD",
    "2269.T": "明治HD",
    "2220.T": "亀田製菓",
    "2264.T": "森永乳業",
    "2267.T": "ヤクルト本社",
    # 商社
    "8001.T": "伊藤忠商事",
    "8002.T": "丸紅",
    "8011.T": "三陽商会",
    "8031.T": "三井物産",
    "8053.T": "住友商事",
    "8058.T": "三菱商事",
    "8015.T": "豊田通商",
    "8016.T": "オンワードHD",
    "8035.T": "東京エレクトロン",
    "8309.T": "三井住友トラスト",
    # 航空・海運・物流
    "9201.T": "日本航空（JAL）",
    "9202.T": "ANAホールディングス",
    "9104.T": "商船三井",
    "9107.T": "川崎汽船",
    "9101.T": "日本郵船",
    "9064.T": "ヤマトHD",
    "9065.T": "山九",
    "9068.T": "丸全昭和運輸",
    "9069.T": "センコーグループHD",
    "9070.T": "トナミHD",
    # エンタメ・ゲーム
    "9684.T": "スクウェア・エニックス",
    "9697.T": "カプコン",
    "7974.T": "任天堂",
    "9766.T": "コナミグループ",
    "7832.T": "バンダイナムコHD",
    "2121.T": "ミクシィ",
    "3765.T": "ガンホー・オンライン",
    "3659.T": "ネクソン",
    "4307.T": "野村総合研究所",
    "4704.T": "トレンドマイクロ",
    # その他優良株
    "4452.T": "花王",
    "4911.T": "資生堂",
    "4927.T": "ポーラ・オルビスHD",
    "7453.T": "良品計画",
    "9843.T": "ニトリHD",
    "2413.T": "エムスリー",
    "6098.T": "リクルートHD",
    "2768.T": "双日",
    "6178.T": "日本郵政",
    "7186.T": "コンコルディアFG",
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
# 個別データ取得（堅牢版）
# ──────────────────────────────────────────────

def _safe_history(ticker: str) -> Optional[pd.DataFrame]:
    try:
        df = yf.Ticker(ticker).history(period="1y")
        if df is None or df.empty:
            return None
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df
    except Exception:
        return None


def _safe_ma(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA25"]  = df["Close"].rolling(25).mean()
    df["MA200"] = df["Close"].rolling(200).mean()
    std = df["Close"].rolling(25).std()
    mid = df["MA25"]
    df["BB_upper2"] = mid + 2 * std
    df["BB_lower2"] = mid - 2 * std
    df["BB_upper3"] = mid + 3 * std
    df["BB_lower3"] = mid - 3 * std
    return df


def _safe_revenue_growth(ticker: str) -> Optional[float]:
    """
    売上高の前年同期比成長率(%)を返す。
    データが取れない場合はNoneを返す（スキップ扱い）。
    """
    try:
        qf = yf.Ticker(ticker).quarterly_financials
        if qf is None or qf.empty:
            return None
        # 複数のキー名に対応
        for key in ["Total Revenue", "Revenue", "Revenues"]:
            if key in qf.index:
                rev = qf.loc[key].dropna().sort_index()
                if len(rev) >= 5:
                    growth = (rev.iloc[-1] - rev.iloc[-5]) / abs(rev.iloc[-5]) * 100
                    return round(growth, 1)
        return None
    except Exception:
        return None


def _safe_eps_uptrend(ticker: str) -> Optional[bool]:
    """
    EPS増加基調かを返す。
    データが取れない場合はNoneを返す（スキップ扱い）。
    """
    try:
        qe = yf.Ticker(ticker).quarterly_earnings
        if qe is None or qe.empty:
            return None
        if "EPS" not in qe.columns:
            return None
        eps = qe["EPS"].dropna().tail(4)
        if len(eps) < 3:
            return None
        diffs = eps.diff().dropna()
        return (diffs > 0).sum() >= len(diffs) * 0.5
    except Exception:
        return None


def _safe_dividend_yield(ticker: str) -> float:
    try:
        dy = yf.Ticker(ticker).info.get("dividendYield")
        return round(dy * 100, 2) if dy else 0.0
    except Exception:
        return 0.0


# ──────────────────────────────────────────────
# 1銘柄スクリーニング
# ──────────────────────────────────────────────

def screen_single(ticker: str, name: str, criteria: ScreenerCriteria) -> Optional[dict]:
    try:
        df_raw = _safe_history(ticker)
        if df_raw is None or len(df_raw) < 30:
            return None

        df = _safe_ma(df_raw)

        # ── テクニカル計算 ──
        recent = df.dropna(subset=["MA25", "MA200"]).tail(5)
        ma25_up  = (recent["MA25"].iloc[-1]  > recent["MA25"].iloc[0])  if len(recent) >= 2 else False
        ma200_up = (recent["MA200"].iloc[-1] > recent["MA200"].iloc[0]) if len(recent) >= 2 else False

        latest_row = df.dropna(subset=["MA25"]).iloc[-1]
        price      = latest_row["Close"]
        deviation  = (price - latest_row["MA25"]) / latest_row["MA25"] * 100

        bb_ok = True
        if "BB_upper3" in df.columns:
            last_bb = df.dropna(subset=["BB_upper3"]).iloc[-1]
            bb_ok   = price < last_bb["BB_upper3"]

        # カップウィズハンドル（簡易）
        closes = df["Close"].dropna()
        cup_detected = False
        if len(closes) >= 125:
            r125     = closes.tail(125)
            cup_high = r125.max()
            cup_idx  = r125.idxmax()
            after    = r125[r125.index > cup_idx]
            if len(after) >= 10:
                depth = (cup_high - after.min()) / cup_high * 100
                prox  = price / cup_high * 100
                cup_detected = (10 <= depth <= 40) and (prox >= 92)

        avg_vol = df_raw["Volume"].tail(20).mean()

        # ── 業績データ（取れない場合はNone＝スキップ） ──
        rev_growth   = _safe_revenue_growth(ticker)
        eps_uptrend  = _safe_eps_uptrend(ticker)
        div_yield    = _safe_dividend_yield(ticker)

        # ── フィルタリング ──
        # テクニカル（データが必ずあるので厳密に判定）
        if criteria.require_ma25_up  and not ma25_up:           return None
        if criteria.require_ma200_up and not ma200_up:          return None
        if abs(deviation) > criteria.max_deviation_pct:         return None
        if criteria.require_below_3sigma and not bb_ok:         return None
        if criteria.require_cup_handle and not cup_detected:    return None

        # 業績（データがある場合のみ判定。Noneはスキップ）
        if rev_growth is not None and rev_growth < criteria.min_revenue_growth_pct:
            return None
        if eps_uptrend is not None and criteria.require_eps_uptrend and not eps_uptrend:
            return None
        if avg_vol < criteria.min_volume:
            return None

        # 配当利回り
        if criteria.use_dividend_filter:
            if div_yield < criteria.min_dividend_yield or div_yield > criteria.max_dividend_yield:
                return None

        # ── スコア計算 ──
        score = 0
        if ma25_up:       score += 10
        if ma200_up:      score += 10
        if abs(deviation) <= 10.0: score += 15
        if bb_ok:         score += 10
        if cup_detected:  score += 15
        # 業績スコア：データがない場合は部分点
        if rev_growth is not None:
            score += 15 if rev_growth >= 25 else (10 if rev_growth >= 10 else 0)
        else:
            score += 7  # データなし→部分点
        if eps_uptrend is True:
            score += 15
        elif eps_uptrend is None:
            score += 7  # データなし→部分点
        if avg_vol >= 50_000: score += 10

        if score < criteria.min_score:
            return None

        label = (
            "🟢 強い買い" if score >= 75 else
            "🟡 買い候補" if score >= 55 else
            "🟠 待ち"     if score >= 35 else
            "🔴 見送り"
        )

        return {
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
    except Exception:
        return None


# ──────────────────────────────────────────────
# 並列スクリーナー実行
# ──────────────────────────────────────────────

def run_screener(
    ticker_dict: dict,
    criteria: ScreenerCriteria,
    progress_callback=None,
) -> pd.DataFrame:
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
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                pass

    if not results:
        return pd.DataFrame()

    df = (pd.DataFrame(results)
          .sort_values("_score_raw", ascending=False)
          .drop(columns=["_score_raw"])
          .reset_index(drop=True))
    df.index += 1
    return df
