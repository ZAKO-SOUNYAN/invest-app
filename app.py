"""app.py — 成長株投資モニター"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import time

from data_loader import fetch_price_history, calc_indicators
from screener import (
    run_screener, search_company,
    PRESET_TICKERS, PRESET_MODES, COMPANY_DICT,
)
from gmail_notifier import send_gmail, send_test_gmail

# ══════════════════════════════════════════════
# ページ設定 & ダークテーマCSS
# ══════════════════════════════════════════════
st.set_page_config(
    page_title="成長株投資モニター",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
/* ── ベース ── */
html, body, [class*="css"] {
    background-color: #0a0e1a !important;
    color: #e0e0e0 !important;
    font-family: 'Segoe UI', 'Hiragino Sans', sans-serif;
}
.stApp { background-color: #0a0e1a; }

/* ── タイトル ── */
.monitor-title {
    font-size: 2rem; font-weight: 900; letter-spacing: 2px;
    color: #00ff88;
    text-shadow: 0 0 20px rgba(0,255,136,0.5);
    margin-bottom: 0;
}
.monitor-sub {
    font-size: 0.85rem; color: #556; letter-spacing: 1px;
    margin-top: 0; margin-bottom: 1rem;
}

/* ── メトリクスカード ── */
.metric-card {
    background: #0d1117;
    border: 1px solid #1e2d3d;
    border-radius: 10px;
    padding: 14px 18px;
    margin-bottom: 8px;
}
.metric-label { font-size:0.72rem; color:#556; letter-spacing:1px; text-transform:uppercase; }
.metric-value { font-size:1.6rem; font-weight:700; color:#00ff88; }
.metric-delta-pos { font-size:0.85rem; color:#00ff88; }
.metric-delta-neg { font-size:0.85rem; color:#ff3366; }

/* ── スコアバー ── */
.score-bar-wrap { background:#1a1f2e; border-radius:6px; height:10px; margin:6px 0; }
.score-bar-fill { height:10px; border-radius:6px; }

/* ── 判定バッジ ── */
.badge-green  { background:#1b5e20; color:#fff; padding:3px 10px;
                border-radius:12px; font-size:0.8rem; font-weight:700; }
.badge-yellow { background:#f57f17; color:#000; padding:3px 10px;
                border-radius:12px; font-size:0.8rem; font-weight:700; }
.badge-orange { background:#bf360c; color:#fff; padding:3px 10px;
                border-radius:12px; font-size:0.8rem; font-weight:700; }
.badge-red    { background:#3c0000; color:#ff6666; padding:3px 10px;
                border-radius:12px; font-size:0.8rem; font-weight:700; }

/* ── 指標行 ── */
.indicator-row {
    display:flex; justify-content:space-between; align-items:center;
    padding: 8px 0; border-bottom: 1px solid #1a1f2e; font-size:0.9rem;
}
.ind-label { color:#8899aa; }
.ind-ok    { color:#00ff88; font-weight:600; }
.ind-ng    { color:#ff3366; font-weight:600; }
.ind-na    { color:#556; }

/* ── タブ ── */
.stTabs [data-baseweb="tab-list"] { background:#0d1117; border-bottom:1px solid #1e2d3d; }
.stTabs [data-baseweb="tab"] { color:#8899aa !important; }
.stTabs [aria-selected="true"] { color:#00ff88 !important;
    border-bottom:2px solid #00ff88 !important; }

/* ── ボタン ── */
.stButton > button {
    background: linear-gradient(135deg, #00ff88, #00cc6a) !important;
    color: #000 !important; font-weight: 700 !important;
    border: none !important; border-radius: 8px !important;
}
.stButton > button:hover { opacity: 0.85 !important; }

/* ── セレクトボックス・スライダー ── */
.stSelectbox div, .stTextInput input, .stNumberInput input {
    background:#0d1117 !important; color:#e0e0e0 !important;
    border-color:#1e2d3d !important;
}
.stSlider div[data-baseweb="slider"] { background:#1a1f2e; }

/* ── チェックボックス ── */
.stCheckbox label { color:#8899aa !important; }

/* ── モードカード ── */
.mode-card {
    background:#0d1117; border:1px solid #1e2d3d;
    border-radius:10px; padding:12px 16px; margin-bottom:6px;
    cursor:pointer;
}
.mode-card-active { border-color:#00ff88 !important; }

/* ── プログレスバー ── */
.stProgress > div > div { background:#00ff88 !important; }

/* ── テーブル ── */
.stDataFrame { border:1px solid #1e2d3d; border-radius:8px; }
thead tr th { background:#0d1117 !important; color:#00ff88 !important; }
tbody tr:hover { background:#1a1f2e !important; }

/* ── expander ── */
.streamlit-expanderHeader {
    background:#0d1117 !important;
    color:#8899aa !important;
    border:1px solid #1e2d3d !important;
    border-radius:8px !important;
}
.streamlit-expanderContent {
    background:#0a0e1a !important;
    border:1px solid #1e2d3d !important;
}

/* ── divider ── */
hr { border-color: #1e2d3d !important; }

/* ── info/warning ── */
.stAlert { background:#0d1117 !important; border-color:#1e2d3d !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════
# ヘッダー
# ══════════════════════════════════════════════
col_t, col_time = st.columns([3,1])
with col_t:
    st.markdown('<p class="monitor-title">📈 成長株投資モニター</p>', unsafe_allow_html=True)
    st.markdown('<p class="monitor-sub">JAPAN EQUITY SCREENING SYSTEM</p>', unsafe_allow_html=True)
with col_time:
    st.markdown(f"<p style='color:#556;font-size:0.8rem;text-align:right;margin-top:1.5rem'>"
                f"Last updated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}</p>",
                unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["🔍 個別銘柄診断", "🎯 スクリーナー", "📧 Gmail通知"])


# ══════════════════════════════════════════════
# ヘルパー：指標の説明（クリックで展開）
# ══════════════════════════════════════════════
INDICATOR_HELP = {
    "MA25上向き": "25日移動平均線（過去25日の終値平均）が右肩上がり。短期トレンドが上昇中であることを示す。",
    "MA200上向き": "200日移動平均線が上向き。機関投資家が重視する長期トレンド指標。この線を上回る銘柄は「強い銘柄」とみなされる。",
    "25日乖離率": "現在値がMA25からどれだけ離れているか(%)。+10%超は過熱サイン。式：(現在値−MA25)÷MA25×100",
    "BB+3σ未達": "ボリンジャーバンド+3σ（統計的な上限）に達していない。到達していると買われすぎで反落リスクが高い。",
    "カップウィズハンドル": "高値→10〜40%調整→再び高値接近のチャートパターン。ブレイクアウト前の典型的な形。",
    "売上高成長率": "前年同期比の売上高成長率。10%以上が買い基準、25%以上で高成長と判断。",
    "EPS増加基調": "1株当たり利益(EPS)が直近3〜4四半期で増加傾向にあるか。利益成長の継続性を示す。",
    "出来高": "直近20日の平均出来高。5万株以上で機関投資家が参加できる流動性があると判断。",
    "配当利回り": "年間配当金÷現在株価×100(%)。配当優先モードでは3%以上が基準。",
    "投資スコア": "各指標を100点満点で総合評価。75点以上→強い買い、55点以上→買い候補、35点以上→待ち。",
}

def show_help(key: str):
    """指標名の隣にクリックで説明が出るexpanderを表示"""
    if key in INDICATOR_HELP:
        with st.expander(f"💡 {key}とは？", expanded=False):
            st.markdown(f"<p style='color:#8899aa;font-size:0.9rem'>{INDICATOR_HELP[key]}</p>",
                        unsafe_allow_html=True)


def score_color(s: int) -> str:
    if s >= 75: return "#00ff88"
    if s >= 55: return "#f9a825"
    if s >= 35: return "#ff6633"
    return "#ff3366"


def ok_ng(flag, na=False) -> str:
    if na:   return "<span class='ind-na'>— データなし</span>"
    if flag: return "<span class='ind-ok'>✅ OK</span>"
    return           "<span class='ind-ng'>❌ NG</span>"


# ══════════════════════════════════════════════
# TAB 1：個別銘柄診断
# ══════════════════════════════════════════════
with tab1:
    st.markdown("#### 銘柄を検索")

    # 検索ボックス（コードまたは会社名）
    col_s, col_btn = st.columns([4,1])
    with col_s:
        query = st.text_input(
            "", placeholder="銘柄コード（例: 7203）または会社名（例: トヨタ）",
            label_visibility="collapsed", key="search_query")
    with col_btn:
        search_btn = st.button("検索", use_container_width=True)

    # 検索結果
    selected_ticker = None
    if query:
        hits = search_company(query)
        if len(hits) == 0:
            # コード直接入力の場合
            raw = query.strip().upper()
            if not raw.endswith(".T"):
                raw = raw + ".T"
            selected_ticker = raw
        elif len(hits) == 1:
            selected_ticker = hits[0][0]
            st.markdown(f"<p style='color:#00ff88;font-size:0.85rem'>✅ {hits[0][1]}（{hits[0][0]}）</p>",
                        unsafe_allow_html=True)
        else:
            options = {f"{n}（{t}）": t for t,n in hits}
            chosen  = st.selectbox("複数の候補が見つかりました", list(options.keys()))
            selected_ticker = options[chosen]

    diag_btn = st.button("📊 診断スタート", type="primary",
                         use_container_width=True, key="diag_btn")

    if diag_btn and selected_ticker:
        ticker = selected_ticker.upper()
        if not ticker.endswith(".T"):
            ticker += ".T"

        with st.spinner("データ取得中..."):
            df_raw = fetch_price_history(ticker)

        if df_raw is None or len(df_raw) < 30:
            st.error(f"❌ {ticker} のデータが取得できませんでした。コードを確認してください。")
        else:
            df    = calc_indicators(df_raw)
            price = df["Close"].iloc[-1]
            prev  = df["Close"].iloc[-2] if len(df) >= 2 else price
            chg   = (price - prev) / prev * 100

            # ── テクニカル計算 ──
            recent   = df.dropna(subset=["MA25","MA200"]).tail(5)
            ma25_up  = recent["MA25"].iloc[-1]  > recent["MA25"].iloc[0]  if len(recent)>=2 else False
            ma200_up = recent["MA200"].iloc[-1] > recent["MA200"].iloc[0] if len(recent)>=2 else False
            last_ma  = df.dropna(subset=["MA25"]).iloc[-1]
            deviation = (price - last_ma["MA25"]) / last_ma["MA25"] * 100

            last_bb = df.dropna(subset=["BB_upper3"]).iloc[-1]
            bb_ok   = price < last_bb["BB_upper3"]
            bw      = last_bb["BB_upper3"] - last_bb["BB_lower3"]
            bb_pos  = (price - last_bb["BB_lower3"]) / bw * 100 if bw > 0 else 50.0

            closes = df["Close"].dropna()
            cup = False; cup_high_val = None
            if len(closes) >= 125:
                r125 = closes.tail(125)
                cup_high_val = r125.max()
                after = r125[r125.index > r125.idxmax()]
                if len(after) >= 10:
                    depth = (cup_high_val - after.min()) / cup_high_val * 100
                    prox  = price / cup_high_val * 100
                    cup   = (10 <= depth <= 40) and (prox >= 92)

            avg_vol = df_raw["Volume"].tail(20).mean()

            score = 0
            if ma25_up:              score += 10
            if ma200_up:             score += 10
            if abs(deviation) <= 10: score += 15
            if bb_ok:                score += 10
            if cup:                  score += 15
            score += 7   # 業績データなし→部分点
            score += 7   # EPSデータなし→部分点
            if avg_vol >= 50_000:    score += 10

            label = ("🟢 強い買い" if score>=75 else
                     "🟡 買い候補" if score>=55 else
                     "🟠 待ち"     if score>=35 else "🔴 見送り")
            sc    = score_color(score)

            # 会社名を辞書から引く
            name = next((n for n,t in COMPANY_DICT.items() if t==ticker), ticker)

            st.markdown("---")

            # ── トップメトリクス ──
            m1,m2,m3,m4 = st.columns(4)
            m1.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>現在値</div>
                <div class='metric-value'>¥{price:,.0f}</div>
                <div class='{"metric-delta-pos" if chg>=0 else "metric-delta-neg"}'>
                {chg:+.2f}% 前日比</div></div>""", unsafe_allow_html=True)
            m2.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>総合スコア</div>
                <div class='metric-value' style='color:{sc}'>{score}点</div>
                <div style='color:{sc};font-size:0.85rem'>{label}</div></div>""",
                unsafe_allow_html=True)
            m3.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>25日乖離率</div>
                <div class='metric-value' style='color:{"#ff3366" if abs(deviation)>10 else "#00ff88"}'>
                {deviation:+.1f}%</div>
                <div style='color:#556;font-size:0.8rem'>10%以内が基準</div></div>""",
                unsafe_allow_html=True)
            m4.markdown(f"""<div class='metric-card'>
                <div class='metric-label'>平均出来高</div>
                <div class='metric-value' style='color:{"#00ff88" if avg_vol>=50000 else "#ff3366"}'>
                {avg_vol/10000:.1f}万株</div>
                <div style='color:#556;font-size:0.8rem'>5万株以上が基準</div></div>""",
                unsafe_allow_html=True)

            # ── スコアプログレスバー ──
            st.markdown(f"""
            <div style='margin:16px 0 8px'>
              <span style='color:#8899aa;font-size:0.8rem'>SCORE</span>
              <span style='color:{sc};font-size:0.8rem;float:right;font-weight:700'>{score}/100</span>
            </div>
            <div class='score-bar-wrap'>
              <div class='score-bar-fill' style='width:{score}%;background:{sc}'></div>
            </div>""", unsafe_allow_html=True)

            st.markdown("---")

            # ── 判定結果（2カラム） ──
            col_l, col_r = st.columns(2)

            with col_l:
                st.markdown("<p style='color:#00ff88;font-size:0.85rem;font-weight:700;"
                            "letter-spacing:1px'>📈 テクニカル</p>", unsafe_allow_html=True)

                items = [
                    ("MA25上向き",      ma25_up,          False),
                    ("MA200上向き",     ma200_up,          False),
                    ("25日乖離率10%以内", abs(deviation)<=10, False),
                    ("BB+3σ未達",      bb_ok,             False),
                    ("カップウィズハンドル", cup,             False),
                ]
                for label_txt, flag, is_na in items:
                    extra = ""
                    if label_txt == "25日乖離率10%以内":
                        extra = f"<span style='color:#556;font-size:0.8rem'> ({deviation:+.1f}%)</span>"
                    if label_txt == "BB+3σ未達":
                        extra = f"<span style='color:#556;font-size:0.8rem'> (バンド内 {bb_pos:.0f}%)</span>"
                    st.markdown(
                        f"<div class='indicator-row'>"
                        f"<span class='ind-label'>{label_txt}</span>"
                        f"{ok_ng(flag, is_na)}{extra}</div>",
                        unsafe_allow_html=True)
                    show_help(label_txt)

            with col_r:
                st.markdown("<p style='color:#00ff88;font-size:0.85rem;font-weight:700;"
                            "letter-spacing:1px'>💹 業績</p>", unsafe_allow_html=True)

                items_r = [
                    ("売上高成長率",   None,  True),
                    ("EPS増加基調",    None,  True),
                    ("出来高",         avg_vol>=50_000, False),
                ]
                for label_txt, flag, is_na in items_r:
                    extra = ""
                    if label_txt == "出来高":
                        extra = f"<span style='color:#556;font-size:0.8rem'> ({avg_vol:,.0f}株)</span>"
                    st.markdown(
                        f"<div class='indicator-row'>"
                        f"<span class='ind-label'>{label_txt}</span>"
                        f"{ok_ng(flag, is_na)}{extra}</div>",
                        unsafe_allow_html=True)
                    show_help(label_txt)

                st.markdown("<br>", unsafe_allow_html=True)
                show_help("投資スコア")

            st.markdown("---")

            # ── チャート ──
            st.markdown("<p style='color:#00ff88;font-size:0.85rem;font-weight:700;"
                        "letter-spacing:1px'>📉 チャート（過去1年）</p>", unsafe_allow_html=True)

            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                vertical_spacing=0.04, row_heights=[0.75, 0.25],
            )
            colors_c = ["#00ff88" if c>=o else "#ff3366"
                        for c,o in zip(df["Close"], df["Open"])]

            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name="株価",
                increasing_line_color="#00ff88", decreasing_line_color="#ff3366",
                increasing_fillcolor="#00ff88", decreasing_fillcolor="#ff3366",
            ), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df["MA25"], name="MA25",
                line=dict(color="#f9a825", width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df["MA200"], name="MA200",
                line=dict(color="#4fc3f7", width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=list(df.index)+list(df.index[::-1]),
                y=list(df["BB_upper2"])+list(df["BB_lower2"][::-1]),
                fill="toself", fillcolor="rgba(0,255,136,0.05)",
                line=dict(color="rgba(0,0,0,0)"), name="BB ±2σ"), row=1, col=1)
            fig.add_trace(go.Scatter(
                x=df.index, y=df["BB_upper3"], name="BB +3σ",
                line=dict(color="#ff3366", width=1, dash="dot")), row=1, col=1)
            if cup_high_val:
                fig.add_hline(y=cup_high_val, line_dash="dash",
                              line_color="#f9a825", line_width=1,
                              annotation_text="カップ高値",
                              annotation_font_color="#f9a825", row=1, col=1)
            fig.add_trace(go.Bar(
                x=df.index, y=df["Volume"], name="出来高",
                marker_color=colors_c, opacity=0.6), row=2, col=1)

            fig.update_layout(
                height=560,
                paper_bgcolor="#0a0e1a",
                plot_bgcolor="#0d1117",
                font=dict(color="#8899aa", size=11),
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", y=1.02, x=0,
                            bgcolor="rgba(0,0,0,0)", font_color="#8899aa"),
                margin=dict(l=0, r=0, t=10, b=0),
            )
            fig.update_xaxes(gridcolor="#1a1f2e", showgrid=True)
            fig.update_yaxes(gridcolor="#1a1f2e", showgrid=True)
            st.plotly_chart(fig, use_container_width=True)

            st.caption("⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。")

    elif not (diag_btn and selected_ticker):
        st.markdown("""
        <div style='text-align:center;padding:60px 0;color:#2a3a4a'>
          <p style='font-size:3rem'>📊</p>
          <p style='font-size:1rem;letter-spacing:2px'>銘柄コードまたは会社名を入力してください</p>
          <p style='font-size:0.8rem'>例：7203、トヨタ、ソニー、6758</p>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════
# TAB 2：スクリーナー
# ══════════════════════════════════════════════
with tab2:
    st.markdown("#### スクリーニングモードを選択")

    # ── モード選択 ──
    mode_names = list(PRESET_MODES.keys())
    selected_mode = st.radio(
        "", mode_names,
        horizontal=True,
        label_visibility="collapsed",
        key="screen_mode",
    )

    # モード説明
    mode_cfg = PRESET_MODES[selected_mode]
    st.markdown(
        f"<div style='background:#0d1117;border:1px solid #1e2d3d;border-left:3px solid #00ff88;"
        f"border-radius:8px;padding:10px 16px;margin:8px 0;color:#8899aa;font-size:0.88rem'>"
        f"{mode_cfg['description']}</div>", unsafe_allow_html=True)

    # ── カスタムモードのみ条件表示 ──
    if selected_mode == "⚙️ カスタム":
        st.markdown("---")
        st.markdown("<p style='color:#00ff88;font-size:0.85rem;font-weight:700'>"
                    "⚙️ 条件を設定してください</p>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**📈 テクニカル**")
            req_ma25  = st.checkbox("MA25が上向き",         value=True,  key="c_ma25")
            req_ma200 = st.checkbox("MA200が上向き",        value=True,  key="c_ma200")
            max_dev   = st.slider("乖離率の上限（%）",      0, 30, 10,   key="c_dev")
            req_bb    = st.checkbox("BB+3σ未達",            value=True,  key="c_bb")
            req_cup   = st.checkbox("カップウィズハンドル", value=False, key="c_cup")
        with c2:
            st.markdown("**💹 業績**")
            min_rev   = st.slider("売上高成長率の下限（%）",-50, 50, 10, key="c_rev")
            req_eps   = st.checkbox("EPS増加基調",          value=True,  key="c_eps")
            min_vol   = st.number_input("最低出来高（株）",  0,1_000_000,50_000,10_000,key="c_vol")
            min_score = st.slider("最低スコア（点）",        0, 100, 30, 5, key="c_score")
        with c3:
            st.markdown("**💰 配当利回り**")
            use_div   = st.checkbox("配当利回りフィルタ",   value=False, key="c_divon")
            min_div   = st.slider("最低（%）",0.0,10.0,0.0,0.1, disabled=not use_div, key="c_dmin")
            max_div   = st.slider("最高（%）",0.0,15.0,10.0,0.1,disabled=not use_div, key="c_dmax")

        criteria = {
            "require_ma25_up":    req_ma25,
            "require_ma200_up":   req_ma200,
            "max_deviation_pct":  float(max_dev),
            "require_bb":         req_bb,
            "require_cup":        req_cup,
            "min_revenue_growth": float(min_rev),
            "require_eps":        req_eps,
            "min_volume":         float(min_vol),
            "use_div_filter":     use_div,
            "min_div":            float(min_div),
            "max_div":            float(max_div),
            "min_score":          min_score,
        }
    else:
        criteria = dict(mode_cfg)

    # ── 銘柄リスト確認 ──
    with st.expander(f"📋 スキャン対象 {len(PRESET_TICKERS)}銘柄を確認する"):
        ticker_list_df = pd.DataFrame(
            [{"コード": t.replace(".T",""), "銘柄名": n}
             for t,n in PRESET_TICKERS.items()]
        )
        st.dataframe(ticker_list_df, use_container_width=True, hide_index=True, height=200)
        extra = st.text_area("銘柄を追加（カンマ or 改行）", placeholder="例: 6532.T, 4385.T", height=60)

    ticker_dict = dict(PRESET_TICKERS)
    if extra.strip():
        for t in extra.replace("\n",",").split(","):
            t = t.strip().upper()
            if t and t not in ticker_dict:
                ticker_dict[t] = ""

    st.markdown("---")
    st.caption(f"対象: **{len(ticker_dict)}銘柄** ／ 並列3スレッド（目安: 約5〜10分）")

    run_btn = st.button(f"🚀 {len(ticker_dict)}銘柄スキャン開始",
                        type="primary", use_container_width=True)

    if run_btn:
        pb     = st.progress(0)
        st_txt = st.empty()
        st_stat = st.empty()

        def on_progress(done, total, fetched, passed):
            pb.progress(int(done/total*100))
            st_txt.markdown(
                f"<p style='color:#8899aa;font-size:0.8rem'>スキャン中... {done}/{total}</p>",
                unsafe_allow_html=True)
            st_stat.markdown(
                f"<p style='color:#00ff88;font-size:0.8rem'>"
                f"取得成功: {fetched}社 　合格: {passed}社</p>",
                unsafe_allow_html=True)

        with st.spinner("スクリーニング実行中..."):
            result_df, stats = run_screener(ticker_dict, criteria, on_progress)

        pb.empty(); st_txt.empty(); st_stat.empty()

        # 統計バー
        col_s1,col_s2,col_s3 = st.columns(3)
        col_s1.markdown(f"<div class='metric-card'><div class='metric-label'>スキャン</div>"
                        f"<div class='metric-value'>{stats['total']}</div></div>", unsafe_allow_html=True)
        col_s2.markdown(f"<div class='metric-card'><div class='metric-label'>データ取得</div>"
                        f"<div class='metric-value' style='color:#f9a825'>{stats['fetched']}</div></div>",
                        unsafe_allow_html=True)
        col_s3.markdown(f"<div class='metric-card'><div class='metric-label'>条件合格</div>"
                        f"<div class='metric-value' style='color:#00ff88'>{stats['passed']}</div></div>",
                        unsafe_allow_html=True)

        if result_df.empty:
            st.markdown("""
            <div style='text-align:center;padding:40px;color:#2a3a4a'>
              <p style='font-size:2rem'>🔍</p>
              <p>条件に合う銘柄が見つかりませんでした</p>
              <p style='font-size:0.85rem'>モードを変更するか、カスタムモードで条件を緩めてみてください</p>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"<p style='color:#00ff88;font-weight:700'>"
                        f"✅ {len(result_df)}銘柄がヒットしました（スコア順）</p>",
                        unsafe_allow_html=True)

            def color_score_cell(val):
                if isinstance(val,(int,float)):
                    if val>=75: return "background-color:#1b5e20;color:white;font-weight:bold"
                    if val>=55: return "background-color:#f57f17;color:black;font-weight:bold"
                    if val>=35: return "background-color:#bf360c;color:white;font-weight:bold"
                return ""

            st.dataframe(
                result_df.style.map(color_score_cell, subset=["スコア"]),
                use_container_width=True)

            col_dl, col_sms = st.columns(2)
            with col_dl:
                csv = result_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button("📥 CSVダウンロード", csv,
                                   "screener_result.csv", "text/csv",
                                   use_container_width=True)
            with col_sms:
                g_addr = st.session_state.get("gmail_address","")
                g_pass = st.session_state.get("gmail_app_password","")
                g_to   = st.session_state.get("gmail_to","")
                if g_addr and g_pass and g_to:
                    mail_score = st.slider("メール送信スコア下限", 0,100,50,5)
                    if st.button("📧 メール送信", type="primary", use_container_width=True):
                        ok, msg = send_gmail(g_addr, g_pass, g_to, result_df, mail_score)
                        st.success(f"✅ {msg}") if ok else st.error(f"❌ {msg}")
                else:
                    st.info("📧 タブ「Gmail通知」で設定するとメール送信できます")

        st.caption("⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。")


# ══════════════════════════════════════════════
# TAB 3：Gmail通知
# ══════════════════════════════════════════════
with tab3:
    st.markdown("#### 📧 Gmail通知設定")
    st.markdown("""
    <div style='background:#0d1117;border:1px solid #1e2d3d;border-radius:8px;padding:16px;margin-bottom:16px'>
      <p style='color:#8899aa;margin:0;font-size:0.9rem'>
        スクリーニング結果を自動でメール通知します。<b style='color:#00ff88'>完全無料・送信数無制限</b>で利用できます。<br>
        Gmailアドレスと「Googleアプリパスワード（16文字）」の2つだけで設定完了です。
      </p>
    </div>""", unsafe_allow_html=True)

    with st.expander("📋 Googleアプリパスワードの取得方法（5分）"):
        st.markdown("""
1. [https://myaccount.google.com](https://myaccount.google.com) を開く
2. 「**セキュリティ**」→「**2段階認証プロセス**」をONにする
3. 検索窓に「**アプリパスワード**」と入力して開く
4. アプリ名に「投資ツール」など入力 →「**作成**」
5. 表示された**16文字のパスワード**をコピーしてここに貼り付ける

⚠️ このパスワードは作成時しか表示されません。必ずコピーしてください。
        """)

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        gmail_in  = st.text_input("送信元Gmailアドレス",
                      value=st.session_state.get("gmail_address",""),
                      placeholder="yourname@gmail.com")
        gmail_to  = st.text_input("送信先アドレス",
                      value=st.session_state.get("gmail_to",""),
                      placeholder="送信先（自分宛でもOK）")
    with c2:
        app_pass  = st.text_input("Googleアプリパスワード（16文字）",
                      value=st.session_state.get("gmail_app_password",""),
                      placeholder="xxxx xxxx xxxx xxxx",
                      type="password")

    col_save, col_test = st.columns(2)
    with col_save:
        if st.button("💾 保存する", type="primary", use_container_width=True):
            if not gmail_in or "@" not in gmail_in:
                st.error("❌ Gmailアドレスが正しくありません")
            elif len(app_pass.replace(" ","")) < 16:
                st.error("❌ アプリパスワードは16文字です")
            elif not gmail_to or "@" not in gmail_to:
                st.error("❌ 送信先アドレスが正しくありません")
            else:
                st.session_state["gmail_address"]      = gmail_in
                st.session_state["gmail_app_password"] = app_pass.replace(" ","")
                st.session_state["gmail_to"]           = gmail_to
                st.success("✅ 保存しました！スクリーナータブからメールを送信できます。")

    with col_test:
        if st.session_state.get("gmail_address"):
            if st.button("📤 テスト送信", use_container_width=True):
                ok, msg = send_test_gmail(
                    st.session_state["gmail_address"],
                    st.session_state["gmail_app_password"],
                    st.session_state["gmail_to"],
                )
                st.success("✅ テスト送信成功！メールを確認してください。") if ok \
                    else st.error(f"❌ {msg}")

    st.markdown("---")
    st.caption("""
⚠️ 入力情報はブラウザのセッションにのみ保存されます。ページを閉じると消えます。
アプリパスワードは他人に見せないでください。
    """)
