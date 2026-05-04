"""app.py — 成長株集中投資 銘柄診断ツール（Streamlit）"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from data_loader import fetch_stock_data, fetch_stock_info, fetch_quarterly_financials
from logic import (
    calc_all_indicators, judge_ma_slope, judge_deviation,
    judge_bollinger, detect_cup_with_handle,
    judge_revenue_growth, judge_eps_trend, judge_volume,
    calc_investment_score,
)
from screener import ScreenerCriteria, run_screener, PRESET_TICKERS

# ──────────────────────────────────────────────
st.set_page_config(page_title="成長株診断ツール", page_icon="📈", layout="wide")
st.title("📈 成長株集中投資 銘柄診断ツール")

tab1, tab2 = st.tabs(["🔍 個別銘柄を診断", "🎯 スクリーナー（50銘柄一括）"])


# ══════════════════════════════════════════════
# TAB 1：個別銘柄診断
# ══════════════════════════════════════════════
with tab1:
    with st.sidebar:
        st.header("🔍 銘柄を入力")
        ticker_input = st.text_input("銘柄コード（例: 6532.T）", value="6532.T")
        analyze_btn  = st.button("診断スタート", type="primary", use_container_width=True)
        st.divider()
        st.markdown("**判定基準**")
        st.markdown("""
- MA25/200上向き：上昇トレンド
- 乖離率10%以内：過熱感なし
- BB+3σ未達：買われすぎでない
- 売上高+10%〜25%以上：高成長
- EPS増加基調：利益成長の継続
- 出来高5万株以上：十分な流動性
        """)

    if analyze_btn and ticker_input:
        ticker = ticker_input.strip().upper()
        with st.spinner(f"{ticker} のデータを取得中..."):
            try:
                df_raw     = fetch_stock_data(ticker, period="1y")
                if df_raw is None or df_raw.empty:
                    st.error("データが取得できませんでした。銘柄コードを確認してください。")
                    st.stop()
                info       = fetch_stock_info(ticker)
                financials = fetch_quarterly_financials(ticker)
            except ValueError as e:
                st.error(str(e)); st.stop()

        df    = calc_all_indicators(df_raw)
        ma_r  = judge_ma_slope(df)
        dev_r = judge_deviation(df)
        bb_r  = judge_bollinger(df)
        cup_r = detect_cup_with_handle(df)
        rev_r = judge_revenue_growth(financials.get("revenue"))
        eps_r = judge_eps_trend(financials.get("eps"))
        vol_r = judge_volume(financials.get("avg_volume", 0))
        sc_r  = calc_investment_score(ma_r, dev_r, bb_r, cup_r, rev_r, eps_r, vol_r)

        latest = df["Close"].iloc[-1]
        chg    = (latest - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100

        st.subheader(f"{info['name']}（{ticker}）")
        c1, c2, c3 = st.columns(3)
        c1.metric("現在値", f"¥{latest:,.0f}")
        c2.metric("前日比", f"{chg:+.2f}%")
        c3.metric("セクター", info.get("sector", "不明"))

        st.divider()
        st.subheader("🏆 総合投資スコア")
        score = sc_r["score"]
        st.progress(score / 100)
        st.markdown(f"**{score} / 100点**　{sc_r['label']}")
        with st.expander("スコア内訳"):
            st.dataframe(
                pd.DataFrame(list(sc_r["breakdown"].items()), columns=["項目","得点"]),
                use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("📊 判定結果")
        def ok(f): return "✅ 買い：○" if f else "❌ 待ち：×"
        l, r = st.columns(2)
        with l:
            st.markdown("**テクニカル**")
            st.write(f"MA25上向き　　　　: {ok(ma_r['ma25_up'])}")
            st.write(f"MA200上向き　　　　: {ok(ma_r['ma200_up'])}")
            st.write(f"25日乖離率　　　　: {ok(dev_r['within_10pct'])}（{dev_r['deviation_pct']:+.1f}%）")
            st.write(f"BB+3σ未達　　　　: {ok(bb_r['below_3sigma'])}（バンド内 {bb_r['bb_position_pct']:.0f}%）")
            st.write(f"カップウィズハンドル: {ok(cup_r.get('detected',False))} 信頼度={cup_r.get('confidence','低')}")
            st.caption(cup_r.get("description",""))
        with r:
            st.markdown("**業績**")
            st.write(f"売上高成長率: {rev_r['label']}")
            if rev_r.get("growth_pct") is not None:
                st.caption(f"前年同期比 {rev_r['growth_pct']:+.1f}%")
            st.write(f"EPSトレンド : {eps_r['trend']}")
            st.write(f"出来高　　　: {vol_r['label']}")

        st.divider()
        st.subheader("📉 チャート（過去1年）")
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                            row_heights=[0.75, 0.25],
                            subplot_titles=("株価 + MA + ボリンジャーバンド", "出来高"))
        fig.add_trace(go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"], name="株価",
            increasing_line_color="#26a69a", decreasing_line_color="#ef5350"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df["MA25"], name="MA25",
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
        if cup_r.get("cup_high"):
            fig.add_hline(y=cup_r["cup_high"], line_dash="dash", line_color="gold",
                          annotation_text="カップ高値", row=1, col=1)
        colors = ["#26a69a" if c>=o else "#ef5350" for c,o in zip(df["Close"], df["Open"])]
        fig.add_trace(go.Bar(x=df.index, y=df["Volume"], name="出来高",
            marker_color=colors, opacity=0.7), row=2, col=1)
        fig.update_layout(height=600, xaxis_rangeslider_visible=False,
            legend=dict(orientation="h", y=1.02, x=0),
            template="plotly_dark", margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。")
    else:
        st.info("👈 左のサイドバーに銘柄コードを入力して「診断スタート」を押してください。")


# ══════════════════════════════════════════════
# TAB 2：スクリーナー
# ══════════════════════════════════════════════
with tab2:
    st.subheader("🎯 カスタムスクリーナー")
    st.caption("条件を自由に設定して、人気日本株50銘柄の中からヒットした銘柄をスコア順に表示します。")

    # ── 銘柄リスト ──
    with st.expander("📋 スキャン対象の50銘柄を確認・編集する"):
        st.markdown("**プリセット50銘柄**（すべて対象）")
        preset_df = pd.DataFrame(
            [{"銘柄コード": t.replace(".T",""), "銘柄名": n}
             for t, n in PRESET_TICKERS.items()]
        )
        st.dataframe(preset_df, use_container_width=True, hide_index=True)

        st.markdown("**銘柄を追加する**（カンマ or 改行で区切る）")
        custom_input = st.text_area("追加銘柄コード", placeholder="例: 6532.T, 7203.T", height=80)

    # 銘柄dictを組み立て
    ticker_dict = dict(PRESET_TICKERS)
    if custom_input.strip():
        for t in custom_input.replace("\n", ",").split(","):
            t = t.strip().upper()
            if t:
                ticker_dict[t] = ticker_dict.get(t, "")

    total_count = len(ticker_dict)
    st.caption(f"スキャン対象: **{total_count}銘柄** ／ 並列8スレッドで処理（目安: 約3〜5分）")

    st.divider()

    # ── スクリーニング条件 ──
    st.markdown("### ⚙️ スクリーニング条件")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**📈 テクニカル**")
        req_ma25  = st.checkbox("MA25が上向き", value=True)
        req_ma200 = st.checkbox("MA200が上向き", value=True)
        max_dev   = st.slider("25日乖離率の上限（%）", 0, 30, 10)
        req_bb    = st.checkbox("BB+3σ未達", value=True)
        req_cup   = st.checkbox("カップウィズハンドル検知", value=False)

    with c2:
        st.markdown("**💹 業績**")
        min_rev   = st.slider("売上高成長率の下限（%）", 0, 50, 10)
        req_eps   = st.checkbox("EPS増加基調", value=True)
        min_vol   = st.number_input("最低出来高（株/日）", 0, 1_000_000, 50_000, 10_000)
        st.markdown("**🏆 最低スコア**")
        min_score = st.slider("最低投資スコア（点）", 0, 100, 40, 5)

    with c3:
        st.markdown("**💰 配当利回り**")
        use_div = st.checkbox("配当利回りでフィルタする", value=False)
        min_div = st.slider("最低配当利回り（%）", 0.0, 10.0, 0.0, 0.1, disabled=not use_div)
        max_div = st.slider("最高配当利回り（%）", 0.0, 15.0, 10.0, 0.1, disabled=not use_div)

    st.divider()
    run_btn = st.button(
        f"🚀 {total_count}銘柄をスキャン開始",
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
            pb.progress(int(done / total * 100))
            st_txt.caption(f"スキャン中... {done}/{total}　最終取得: {t}")

        with st.spinner("スクリーニング実行中..."):
            result_df = run_screener(ticker_dict, criteria, progress_callback=on_progress)

        pb.empty()
        st_txt.empty()

        if result_df.empty:
            st.warning("条件に合う銘柄が見つかりませんでした。条件を少し緩めてみてください。")
        else:
            st.success(f"✅ {len(result_df)}銘柄がヒットしました（スコア順）")

            def color_score(val):
                if val >= 75: return "background-color:#1b5e20;color:white"
                if val >= 55: return "background-color:#f9a825;color:black"
                if val >= 35: return "background-color:#e65100;color:white"
                return ""

            st.dataframe(
                result_df.style.applymap(color_score, subset=["スコア"]),
                use_container_width=True)

            csv = result_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("📥 CSVでダウンロード", csv, "screener_result.csv", "text/csv")

    st.caption("⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。")
