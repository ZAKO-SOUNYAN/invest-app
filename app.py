"""app.py — 成長株集中投資 銘柄診断ツール（Streamlit）"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import yfinance as yf
import numpy as np

from screener import ScreenerCriteria, run_screener, PRESET_TICKERS

# ──────────────────────────────────────────────
# ページ設定
# ──────────────────────────────────────────────
st.set_page_config(page_title="成長株診断ツール", page_icon="📈", layout="wide")
st.title("📈 成長株集中投資 銘柄診断ツール")

tab1, tab2, tab3 = st.tabs(["🔍 個別銘柄を診断", "🎯 スクリーナー（300銘柄一括）", "📖 指標の説明"])


# ══════════════════════════════════════════════════
# 共通：テクニカル計算
# ══════════════════════════════════════════════════
def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
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


def get_history(ticker: str):
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


# ══════════════════════════════════════════════════
# TAB 1：個別銘柄診断
# ══════════════════════════════════════════════════
with tab1:
    with st.sidebar:
        st.header("🔍 銘柄を入力")
        ticker_input = st.text_input(
            "銘柄コード（例: 6532.T）", value="7203.T",
            help="東証銘柄は末尾に .T を付けてください")
        analyze_btn = st.button("診断スタート", type="primary", use_container_width=True)

    if analyze_btn and ticker_input:
        ticker = ticker_input.strip().upper()

        with st.spinner(f"{ticker} のデータを取得中..."):
            df_raw = get_history(ticker)
            if df_raw is None or len(df_raw) < 30:
                st.error("データが取得できませんでした。銘柄コードを確認してください。（例: 7203.T）")
                st.stop()

            stock = yf.Ticker(ticker)
            info  = stock.info or {}
            name  = info.get("longName") or info.get("shortName", ticker)

            # 四半期売上高
            rev_growth = None
            try:
                qf = stock.quarterly_financials
                if qf is not None and not qf.empty:
                    for key in ["Total Revenue", "Revenue"]:
                        if key in qf.index:
                            rev = qf.loc[key].dropna().sort_index()
                            if len(rev) >= 5:
                                rev_growth = round(
                                    (rev.iloc[-1] - rev.iloc[-5]) / abs(rev.iloc[-5]) * 100, 1)
                            break
            except Exception:
                pass

            # EPS
            eps_uptrend = None
            try:
                qe = stock.quarterly_earnings
                if qe is not None and not qe.empty and "EPS" in qe.columns:
                    eps = qe["EPS"].dropna().tail(4)
                    if len(eps) >= 3:
                        diffs = eps.diff().dropna()
                        eps_uptrend = (diffs > 0).sum() >= len(diffs) * 0.5
            except Exception:
                pass

            # 配当利回り
            div_yield = 0.0
            try:
                dy = info.get("dividendYield")
                div_yield = round(dy * 100, 2) if dy else 0.0
            except Exception:
                pass

            avg_vol = df_raw["Volume"].tail(20).mean()

        df = calc_indicators(df_raw)

        # ── テクニカル判定 ──
        recent   = df.dropna(subset=["MA25","MA200"]).tail(5)
        ma25_up  = recent["MA25"].iloc[-1]  > recent["MA25"].iloc[0]  if len(recent)>=2 else False
        ma200_up = recent["MA200"].iloc[-1] > recent["MA200"].iloc[0] if len(recent)>=2 else False

        last     = df.dropna(subset=["MA25"]).iloc[-1]
        price    = last["Close"]
        deviation = (price - last["MA25"]) / last["MA25"] * 100

        bb_ok = True
        if "BB_upper3" in df.columns:
            last_bb = df.dropna(subset=["BB_upper3"]).iloc[-1]
            bb_ok   = price < last_bb["BB_upper3"]
            bb_pos  = (price - last_bb["BB_lower3"]) / (last_bb["BB_upper3"] - last_bb["BB_lower3"]) * 100
        else:
            bb_pos = 50.0

        # カップウィズハンドル
        closes = df["Close"].dropna()
        cup_detected = False
        cup_high_val = None
        if len(closes) >= 125:
            r125     = closes.tail(125)
            cup_high_val = r125.max()
            cup_idx  = r125.idxmax()
            after    = r125[r125.index > cup_idx]
            if len(after) >= 10:
                depth = (cup_high_val - after.min()) / cup_high_val * 100
                prox  = price / cup_high_val * 100
                cup_detected = (10 <= depth <= 40) and (prox >= 92)

        # ── スコア計算 ──
        score = 0
        if ma25_up:  score += 10
        if ma200_up: score += 10
        if abs(deviation) <= 10: score += 15
        if bb_ok:    score += 10
        if cup_detected: score += 15
        if rev_growth is not None:
            score += 15 if rev_growth >= 25 else (10 if rev_growth >= 10 else 0)
        else:
            score += 7
        if eps_uptrend is True:  score += 15
        elif eps_uptrend is None: score += 7
        if avg_vol >= 50_000:    score += 10

        label = (
            "🟢 強い買いシグナル" if score >= 75 else
            "🟡 買い候補（要確認）" if score >= 55 else
            "🟠 待ち" if score >= 35 else
            "🔴 見送り"
        )

        # ── 表示 ──
        latest = df["Close"].iloc[-1]
        prev   = df["Close"].iloc[-2]
        chg    = (latest - prev) / prev * 100

        st.subheader(f"{name}（{ticker}）")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("現在値",    f"¥{latest:,.0f}")
        c2.metric("前日比",    f"{chg:+.2f}%")
        c3.metric("配当利回り", f"{div_yield:.2f}%")
        c4.metric("平均出来高", f"{avg_vol:,.0f}株")

        st.divider()
        st.subheader("🏆 総合投資スコア")
        st.progress(score / 100)
        st.markdown(f"### {score} / 100点　　{label}")

        breakdown = {
            "MA25上向き":       10 if ma25_up else 0,
            "MA200上向き":      10 if ma200_up else 0,
            "25日乖離率10%以内": 15 if abs(deviation)<=10 else 0,
            "BB+3σ未達":       10 if bb_ok else 0,
            "カップウィズハンドル": 15 if cup_detected else 0,
            "売上高成長率":     (15 if (rev_growth or 0)>=25 else 10 if (rev_growth or 0)>=10 else 7 if rev_growth is None else 0),
            "EPS増加基調":      (15 if eps_uptrend else 7 if eps_uptrend is None else 0),
            "出来高5万株以上":  10 if avg_vol>=50_000 else 0,
        }
        with st.expander("スコア内訳を見る"):
            bd_df = pd.DataFrame(list(breakdown.items()), columns=["項目","得点"])
            st.dataframe(bd_df, use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("📊 判定結果")
        def ok(f): return "✅ 買い：○" if f else "❌ 待ち：×"
        def ok3(v): return "✅ 買い：○" if v is True else "⬜ データなし" if v is None else "❌ 待ち：×"

        l, r = st.columns(2)
        with l:
            st.markdown("**📈 テクニカル**")
            st.write(f"MA25上向き　　　　　: {ok(ma25_up)}")
            st.write(f"MA200上向き　　　　　: {ok(ma200_up)}")
            st.write(f"25日乖離率　　　　　: {ok(abs(deviation)<=10)}（{deviation:+.1f}%）")
            st.write(f"BB+3σ未達　　　　　: {ok(bb_ok)}（バンド内 {bb_pos:.0f}%）")
            st.write(f"カップウィズハンドル　: {ok(cup_detected)}")
        with r:
            st.markdown("**💹 業績**")
            if rev_growth is not None:
                rev_ok = rev_growth >= 10
                st.write(f"売上高成長率: {ok(rev_ok)}（前年同期比 {rev_growth:+.1f}%）")
            else:
                st.write("売上高成長率: ⬜ データなし")
            st.write(f"EPSトレンド : {ok3(eps_uptrend)}")
            st.write(f"出来高　　　: {ok(avg_vol>=50_000)}（{avg_vol:,.0f}株/日）")
            st.write(f"配当利回り　: {div_yield:.2f}%")

        st.divider()
        st.subheader("📉 チャート（過去1年）")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                            row_heights=[0.75, 0.25],
                            subplot_titles=("株価 + 移動平均 + ボリンジャーバンド", "出来高"))

        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"],  close=df["Close"], name="株価",
            increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MA25"],  name="MA25",
            line=dict(color="orange", width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MA200"], name="MA200",
            line=dict(color="royalblue", width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=list(df.index)+list(df.index[::-1]),
            y=list(df["BB_upper2"])+list(df["BB_lower2"][::-1]),
            fill="toself", fillcolor="rgba(128,128,128,0.1)",
            line=dict(color="rgba(0,0,0,0)"), name="BB ±2σ"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["BB_upper3"], name="BB +3σ",
            line=dict(color="red", width=1, dash="dot")), row=1, col=1)
        if cup_high_val:
            fig.add_hline(y=cup_high_val, line_dash="dash", line_color="gold",
                          annotation_text="カップ高値", row=1, col=1)
        colors = ["#26a69a" if c>=o else "#ef5350"
                  for c,o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="出来高",
            marker_color=colors, opacity=0.7), row=2, col=1)
        fig.update_layout(height=600, xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.02, x=0),
            template="plotly_dark", margin=dict(l=0,r=0,t=30,b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。")

    else:
        st.info("👈 左のサイドバーに銘柄コードを入力して「診断スタート」を押してください。")
        st.markdown("""
**銘柄コードの入力例**
| 銘柄名 | コード |
|--------|--------|
| トヨタ自動車 | 7203.T |
| ソニーグループ | 6758.T |
| キーエンス | 6861.T |
| ファーストリテイリング | 9983.T |
| 東京エレクトロン | 8035.T |
        """)


# ══════════════════════════════════════════════════
# TAB 2：スクリーナー
# ══════════════════════════════════════════════════
with tab2:
    st.subheader("🎯 カスタムスクリーナー")
    st.caption("条件を設定して、日本株300銘柄の中からヒットした銘柄をスコア順に表示します。")

    # 銘柄リスト確認
    with st.expander(f"📋 スキャン対象の{len(PRESET_TICKERS)}銘柄を確認する"):
        preset_df = pd.DataFrame(
            [{"銘柄コード": t.replace(".T",""), "銘柄名": n}
             for t, n in PRESET_TICKERS.items()])
        st.dataframe(preset_df, use_container_width=True, hide_index=True)
        st.markdown("**銘柄を追加する**（カンマ or 改行で区切る）")
        custom_input = st.text_area("追加銘柄コード",
            placeholder="例: 6532.T, 4385.T", height=70, key="custom")

    ticker_dict = dict(PRESET_TICKERS)
    if "custom" in st.session_state and st.session_state.custom.strip():
        for t in st.session_state.custom.replace("\n",",").split(","):
            t = t.strip().upper()
            if t:
                ticker_dict[t] = ticker_dict.get(t, "")

    st.caption(f"スキャン対象: **{len(ticker_dict)}銘柄** ／ 並列処理（目安: 約5〜10分）")
    st.divider()

    # ── 条件設定 ──
    st.markdown("### ⚙️ スクリーニング条件")
    st.caption("💡 各指標の意味は「📖 指標の説明」タブで確認できます。")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**📈 テクニカル**")
        req_ma25  = st.checkbox("MA25が上向き",      value=True)
        req_ma200 = st.checkbox("MA200が上向き",     value=True)
        max_dev   = st.slider("25日乖離率の上限（%）", 0, 30, 10)
        req_bb    = st.checkbox("BB+3σ未達",         value=True)
        req_cup   = st.checkbox("カップウィズハンドル検知", value=False)

    with c2:
        st.markdown("**💹 業績**")
        min_rev   = st.slider("売上高成長率の下限（%）", 0, 50, 10)
        req_eps   = st.checkbox("EPS増加基調",       value=True)
        min_vol   = st.number_input("最低出来高（株/日）",
                       0, 1_000_000, 50_000, 10_000)
        st.markdown("**🏆 最低スコア**")
        min_score = st.slider("最低スコア（点）", 0, 100, 30, 5)

    with c3:
        st.markdown("**💰 配当利回り**")
        use_div = st.checkbox("配当利回りでフィルタする", value=False)
        min_div = st.slider("最低配当利回り（%）", 0.0, 10.0, 0.0, 0.1,
                            disabled=not use_div)
        max_div = st.slider("最高配当利回り（%）", 0.0, 15.0, 10.0, 0.1,
                            disabled=not use_div)

    st.divider()
    run_btn = st.button(f"🚀 {len(ticker_dict)}銘柄をスキャン開始",
                        type="primary", use_container_width=True)

    if run_btn:
        criteria = ScreenerCriteria(
            require_ma25_up=req_ma25,
            require_ma200_up=req_ma200,
            max_deviation_pct=float(max_dev),
            require_below_3sigma=req_bb,
            require_cup_handle=req_cup,
            min_revenue_growth_pct=float(min_rev),
            require_eps_uptrend=req_eps,
            min_volume=float(min_vol),
            use_dividend_filter=use_div,
            min_dividend_yield=float(min_div),
            max_dividend_yield=float(max_div),
            min_score=min_score,
        )

        pb     = st.progress(0)
        st_txt = st.empty()

        def on_progress(done, total, t):
            pb.progress(int(done/total*100))
            st_txt.caption(f"スキャン中... {done}/{total}　直近: {t}")

        with st.spinner("スクリーニング実行中..."):
            result_df = run_screener(ticker_dict, criteria, progress_callback=on_progress)

        pb.empty()
        st_txt.empty()

        if result_df.empty:
            st.warning("""
条件に合う銘柄が見つかりませんでした。以下を試してみてください。
- 「最低スコア」を下げる（例: 30点以上）
- 「売上高成長率」を0%に下げる
- 「EPS増加基調」のチェックを外す
- 「MA200が上向き」のチェックを外す
            """)
        else:
            st.success(f"✅ {len(result_df)}銘柄がヒットしました（スコア順）")

            def color_score(val):
                if isinstance(val, (int, float)):
                    if val >= 75: return "background-color:#1b5e20;color:white"
                    if val >= 55: return "background-color:#f9a825;color:black"
                    if val >= 35: return "background-color:#bf360c;color:white"
                return ""

            st.dataframe(
                result_df.style.applymap(color_score, subset=["スコア"]),
                use_container_width=True)

            csv = result_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("📥 CSVでダウンロード", csv,
                               "screener_result.csv", "text/csv")

    st.caption("⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。")


# ══════════════════════════════════════════════════
# TAB 3：指標の説明
# ══════════════════════════════════════════════════
with tab3:
    st.subheader("📖 各指標の意味と使い方")

    st.markdown("---")
    st.markdown("## 📈 テクニカル指標")

    st.markdown("### 1. MA25（25日移動平均線）が上向き")
    st.info("""
**移動平均線とは？**
過去N日間の終値の平均を線でつないだものです。

**25日線（約1ヶ月）が上向き**とは、短期的な株価トレンドが上昇していることを意味します。
下降トレンドの銘柄よりも、上昇トレンドの銘柄のほうが「乗りやすい波」に乗れます。

📌 **判定基準**: 直近5日間でMA25が上昇していれば「○」
    """)

    st.markdown("### 2. MA200（200日移動平均線）が上向き")
    st.info("""
**200日線（約10ヶ月）が上向き**とは、長期的な株価トレンドが上昇していることを意味します。
機関投資家（大きな資金を動かすプロ）が重視する指標で、200日線より上にある銘柄は
「強い銘柄」とみなされます。

📌 **判定基準**: 直近5日間でMA200が上昇していれば「○」
    """)

    st.markdown("### 3. 25日乖離率（かいりりつ）")
    st.info("""
**乖離率とは？**
現在の株価が移動平均線からどれだけ離れているかを%で表したものです。

```
乖離率 = (現在値 − MA25) ÷ MA25 × 100
```

乖離率が**大きすぎる（+10%超）**と、株価が短期的に上がりすぎており、
**反落（急激な値下がり）のリスク**があります。
10%以内であれば「適度な位置」と判断します。

📌 **判定基準**: 乖離率が±10%以内なら「○」
    """)

    st.markdown("### 4. ボリンジャーバンド +3σ未達")
    st.info("""
**ボリンジャーバンドとは？**
移動平均線を中心に、統計的なばらつき（σ＝シグマ）を上下に重ねたバンドです。

- **±2σ**: 株価はこの範囲内に収まる確率が約95%
- **±3σ**: 株価はこの範囲内に収まる確率が約99.7%

株価が**+3σに達している**場合、異常なほど買われすぎており、
反落リスクが非常に高い状態です。+3σ未満であれば「まだ余地あり」と判断します。

📌 **判定基準**: 現在値がBB+3σより下なら「○」
    """)

    st.markdown("### 5. カップウィズハンドル")
    st.info("""
**カップウィズハンドルとは？**
アメリカの投資家ウィリアム・オニールが提唱した、上昇前に現れるチャートパターンです。

```
形状イメージ:
高値 ───────         ← ブレイクポイント
      ＼       ／
        ＼   ／  ← カップ（丸い底）
          ＼／
           ← ハンドル（小さな調整）
```

① 高値をつける
② 10〜40%程度じっくり調整（カップ形成）
③ 再び高値に近づく（ブレイクアウト候補）

この形を経て高値をブレイクした銘柄は、大きく上昇することが多いとされています。

📌 **判定基準**: 過去6ヶ月の調整幅10〜40%・現在値が高値の92%以上で「検知」
    """)

    st.markdown("---")
    st.markdown("## 💹 業績指標")

    st.markdown("### 6. 売上高成長率（前年同期比）")
    st.info("""
**売上高とは？**
会社が商品・サービスを販売して得た収入の合計です。

**前年同期比**とは、今年の同じ四半期と昨年の同じ四半期を比べた成長率です。

```
成長率 = (今期売上 − 前年同期売上) ÷ 前年同期売上 × 100
```

「成長株」として注目されるには、**最低10%、理想は25%以上**の成長が目安です。

📌 **配点**: 25%以上→15点 / 10%以上→10点 / 10%未満→0点
⚠️ データが取得できない銘柄は部分点（7点）が付きます
    """)

    st.markdown("### 7. EPS（1株当たり利益）増加基調")
    st.info("""
**EPSとは？（Earnings Per Share）**
会社の純利益を発行済み株式数で割った数値です。

```
EPS = 純利益 ÷ 発行済み株式数
```

EPSが**連続して増加**していることは、会社の稼ぐ力が伸びていることを示します。
売上が増えても利益が増えていなければ、経営効率が悪化している可能性があります。

📌 **判定基準**: 直近3〜4四半期のうち半数以上で増加していれば「○」
⚠️ データが取得できない銘柄は部分点（7点）が付きます
    """)

    st.markdown("### 8. 出来高（5万株/日以上）")
    st.info("""
**出来高とは？**
1日に売買された株の総数です。

出来高が多いほど「多くの投資家が取引している」ことを意味し、
**機関投資家（大口の買い手）が参加できる流動性**があることを示します。

出来高が少ない銘柄は、買いたい時に買えない・売りたい時に売れない
「流動性リスク」があります。

📌 **判定基準**: 直近20日の平均出来高が5万株以上で「○」
    """)

    st.markdown("---")
    st.markdown("## 💰 配当利回り")

    st.info("""
**配当利回りとは？**
株価に対して、1年間に受け取れる配当金の割合です。

```
配当利回り = 年間配当金 ÷ 現在の株価 × 100
```

- **高配当株を狙う場合**: 利回り3〜5%以上を目安に設定
- **成長株を狙う場合**: 配当よりも株価上昇を重視するため、0〜2%程度でも問題なし
- **高すぎる場合注意**: 利回り8%超は「株価が大幅下落している」サインのこともあります

📌 **スクリーナーでの使い方**: 「配当利回りでフィルタする」をONにして範囲を指定
    """)

    st.markdown("---")
    st.markdown("## 🏆 総合スコアの見方")

    score_df = pd.DataFrame({
        "スコア範囲": ["75〜100点", "55〜74点", "35〜54点", "0〜34点"],
        "判定":       ["🟢 強い買いシグナル", "🟡 買い候補（要確認）", "🟠 待ち", "🔴 見送り"],
        "意味":       [
            "ほぼ全ての条件を満たす優良候補。積極的に調査する価値あり。",
            "多くの条件を満たす。チャートや業績を詳しく確認してから検討。",
            "条件を一部満たすが不十分。もう少し相場が育つのを待つ。",
            "現時点では条件不足。ウォッチリストに入れて様子見。",
        ]
    })
    st.dataframe(score_df, use_container_width=True, hide_index=True)

    st.caption("⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。投資判断はご自身の責任において行ってください。")
