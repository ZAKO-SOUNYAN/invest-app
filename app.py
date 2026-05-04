"""app.py — 成長株集中投資 銘柄診断ツール（Streamlit）"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

from data_loader import fetch_stock_data, fetch_stock_info, fetch_quarterly_financials
from logic import (
    calc_all_indicators,
    judge_ma_slope,
    judge_deviation,
    judge_bollinger,
    detect_cup_with_handle,
    judge_revenue_growth,
    judge_eps_trend,
    judge_volume,
    calc_investment_score,
)

# ──────────────────────────────────────────────
# ページ設定
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="成長株診断ツール",
    page_icon="📈",
    layout="wide",
)

st.title("📈 成長株集中投資 銘柄診断ツール")
st.caption("業績・テクニカル指標をもとに日本株の投資判定を行います。")

# ──────────────────────────────────────────────
# サイドバー：銘柄入力
# ──────────────────────────────────────────────
with st.sidebar:
    st.header("🔍 銘柄を入力")
    ticker_input = st.text_input(
        "銘柄コード（例: 6532.T, 7203.T）",
        value="6532.T",
        help="東証銘柄は末尾に .T を付けてください。",
    )
    analyze_btn = st.button("診断スタート", type="primary", use_container_width=True)

    st.divider()
    st.markdown("**判定基準の説明**")
    st.markdown(
        """
- **MA25/200上向き**: 株価トレンドが上昇中
- **乖離率10%以内**: 移動平均からの過熱感なし
- **BB+3σ未達**: 短期的な買われすぎでない
- **売上高+10%〜25%以上**: 高成長企業
- **EPS増加基調**: 利益成長の継続性
- **出来高5万株以上**: 機関投資家が参加できる流動性
        """
    )

# ──────────────────────────────────────────────
# メイン処理
# ──────────────────────────────────────────────
if analyze_btn and ticker_input:
    ticker = ticker_input.strip().upper()

    # ① データ取得
    with st.spinner(f"{ticker} のデータを取得中..."):
        try:
            df_raw = fetch_stock_data(ticker, period="1y")
            if df_raw is None or df_raw.empty:
                st.error("株価データが取得できませんでした。銘柄コードを確認してください。")
                st.stop()

            info = fetch_stock_info(ticker)
            financials = fetch_quarterly_financials(ticker)
        except ValueError as e:
            st.error(str(e))
            st.stop()

    # ② 指標計算
    df = calc_all_indicators(df_raw)

    # ③ 各判定
    ma_result       = judge_ma_slope(df)
    deviation_result = judge_deviation(df)
    bb_result        = judge_bollinger(df)
    cup_result       = detect_cup_with_handle(df)
    revenue_result   = judge_revenue_growth(financials.get("revenue"))
    eps_result       = judge_eps_trend(financials.get("eps"))
    volume_result    = judge_volume(financials.get("avg_volume", 0))

    # ④ 総合スコア
    score_result = calc_investment_score(
        ma_result, deviation_result, bb_result, cup_result,
        revenue_result, eps_result, volume_result,
    )

    # ──────────────────────────────────────────
    # 表示：銘柄ヘッダー
    # ──────────────────────────────────────────
    latest_close = df["Close"].iloc[-1]
    prev_close   = df["Close"].iloc[-2]
    change_pct   = (latest_close - prev_close) / prev_close * 100

    st.subheader(f"{info['name']}（{ticker}）")
    col_price, col_change, col_sector = st.columns(3)
    col_price.metric("現在値", f"¥{latest_close:,.0f}")
    col_change.metric("前日比", f"{change_pct:+.2f}%")
    col_sector.metric("セクター", info.get("sector", "不明"))

    st.divider()

    # ──────────────────────────────────────────
    # 表示：総合スコア
    # ──────────────────────────────────────────
    st.subheader("🏆 総合投資スコア")
    score = score_result["score"]
    label = score_result["label"]

    progress_col, label_col = st.columns([2, 1])
    with progress_col:
        st.progress(score / 100)
        st.markdown(f"**{score} / 100点**")
    with label_col:
        st.markdown(f"### {label}")

    # スコア内訳
    with st.expander("スコア内訳を見る"):
        breakdown = score_result["breakdown"]
        bd_df = pd.DataFrame(
            list(breakdown.items()), columns=["項目", "得点"]
        )
        st.dataframe(bd_df, use_container_width=True, hide_index=True)

    st.divider()

    # ──────────────────────────────────────────
    # 表示：判定結果一覧（2カラム）
    # ──────────────────────────────────────────
    st.subheader("📊 判定結果")
    left, right = st.columns(2)

    def ok(flag: bool) -> str:
        return "✅ 買い：○" if flag else "❌ 待ち：×"

    with left:
        st.markdown("**テクニカル**")
        st.write(f"MA25上向き　　: {ok(ma_result['ma25_up'])}")
        st.write(f"MA200上向き　　: {ok(ma_result['ma200_up'])}")
        st.write(
            f"25日乖離率　　: {ok(deviation_result['within_10pct'])}  "
            f"（{deviation_result['deviation_pct']:+.1f}%）"
        )
        st.write(
            f"BB+3σ未達　　: {ok(bb_result['below_3sigma'])}  "
            f"（バンド内位置 {bb_result['bb_position_pct']:.0f}%）"
        )
        # カップウィズハンドル
        cup_ok = cup_result.get("detected", False)
        st.write(
            f"カップウィズハンドル: {ok(cup_ok)}  "
            f"信頼度={cup_result.get('confidence','低')}"
        )
        st.caption(cup_result.get("description", ""))

    with right:
        st.markdown("**業績**")
        st.write(f"売上高成長率　: {revenue_result['label']}")
        if revenue_result.get("growth_pct") is not None:
            st.caption(f"前年同期比 {revenue_result['growth_pct']:+.1f}%")
        st.write(f"EPSトレンド　 : {eps_result['trend']}")
        st.write(f"出来高　　　　: {volume_result['label']}")

    st.divider()

    # ──────────────────────────────────────────
    # チャート（Plotly）
    # ──────────────────────────────────────────
    st.subheader("📉 チャート（過去1年）")

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.75, 0.25],
        subplot_titles=("株価 + 移動平均 + ボリンジャーバンド", "出来高"),
    )

    # ローソク足
    fig.add_trace(
        go.Candlestick(
            x=df.index, open=df["Open"], high=df["High"],
            low=df["Low"], close=df["Close"],
            name="株価", increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        ),
        row=1, col=1,
    )

    # MA25
    fig.add_trace(
        go.Scatter(x=df.index, y=df["MA25"], name="MA25",
                   line=dict(color="orange", width=1.5)),
        row=1, col=1,
    )

    # MA200
    fig.add_trace(
        go.Scatter(x=df.index, y=df["MA200"], name="MA200",
                   line=dict(color="royalblue", width=1.5)),
        row=1, col=1,
    )

    # ボリンジャーバンド（±2σ）
    fig.add_trace(
        go.Scatter(
            x=list(df.index) + list(df.index[::-1]),
            y=list(df["BB_upper2"]) + list(df["BB_lower2"][::-1]),
            fill="toself", fillcolor="rgba(128,128,128,0.1)",
            line=dict(color="rgba(0,0,0,0)"), name="BB ±2σ", showlegend=True,
        ),
        row=1, col=1,
    )

    # ボリンジャーバンド（+3σ ライン）
    fig.add_trace(
        go.Scatter(x=df.index, y=df["BB_upper3"], name="BB +3σ",
                   line=dict(color="red", width=1, dash="dot")),
        row=1, col=1,
    )

    # カップ高値ライン
    if cup_result.get("cup_high"):
        fig.add_hline(
            y=cup_result["cup_high"],
            line_dash="dash", line_color="gold",
            annotation_text="カップ高値",
            row=1, col=1,
        )

    # 出来高
    colors = ["#26a69a" if c >= o else "#ef5350"
              for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(
        go.Bar(x=df.index, y=df["Volume"], name="出来高",
               marker_color=colors, opacity=0.7),
        row=2, col=1,
    )

    fig.update_layout(
        height=600,
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", y=1.02, x=0),
        template="plotly_dark",
        margin=dict(l=0, r=0, t=30, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    # ──────────────────────────────────────────
    # 免責事項
    # ──────────────────────────────────────────
    st.caption(
        "⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。"
        "投資判断はご自身の責任において行ってください。"
    )

else:
    # 初期画面
    st.info("👈 左のサイドバーに銘柄コードを入力して「診断スタート」を押してください。")
    st.markdown(
        """
### 使い方
1. サイドバーに銘柄コードを入力（例: `6532.T`, `7203.T`, `9984.T`）
2. 「診断スタート」をクリック
3. テクニカル・業績の判定結果と総合スコアが表示されます

### 判定項目
| カテゴリ | 項目 | 配点 |
|---------|------|------|
| テクニカル | MA25上向き | 10点 |
| テクニカル | MA200上向き | 10点 |
| テクニカル | 25日乖離率10%以内 | 15点 |
| テクニカル | BB+3σ未達 | 10点 |
| テクニカル | カップウィズハンドル | 15点 |
| 業績 | 売上高前年同期比+10%以上 | 15点 |
| 業績 | EPS増加基調 | 15点 |
| 業績 | 出来高5万株以上 | 10点 |
        """
    )
