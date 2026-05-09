"""app.py — 成長株集中投資 銘柄診断ツール（Streamlit）"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import yfinance as yf
import time

from screener import ScreenerCriteria, run_screener, PRESET_TICKERS
from gmail_notifier import send_gmail, send_test_gmail

st.set_page_config(page_title="成長株診断ツール", page_icon="📈", layout="wide")
st.title("📈 成長株集中投資 銘柄診断ツール")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔍 個別銘柄を診断",
    "🎯 スクリーナー（300銘柄）",
    "📧 Gmail通知設定",
    "📖 指標の説明",
])


# ──────────────────────────────────────────────
# 共通関数
# ──────────────────────────────────────────────
def get_history(ticker: str):
    for _ in range(2):
        try:
            df = yf.Ticker(ticker).history(period="1y")
            if df is not None and not df.empty:
                df.index = pd.to_datetime(df.index)
                if df.index.tz is not None:
                    df.index = df.index.tz_localize(None)
                return df
        except Exception:
            time.sleep(1)
    return None


def calc_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA25"]      = df["Close"].rolling(25).mean()
    df["MA200"]     = df["Close"].rolling(200).mean()
    std             = df["Close"].rolling(25).std()
    df["BB_upper2"] = df["MA25"] + 2 * std
    df["BB_lower2"] = df["MA25"] - 2 * std
    df["BB_upper3"] = df["MA25"] + 3 * std
    df["BB_lower3"] = df["MA25"] - 3 * std
    return df


# ══════════════════════════════════════════════
# TAB 1：個別銘柄診断
# ══════════════════════════════════════════════
with tab1:
    with st.sidebar:
        st.header("🔍 銘柄を入力")
        ticker_input = st.text_input("銘柄コード（例: 7203.T）", value="7203.T")
        analyze_btn  = st.button("診断スタート", type="primary", use_container_width=True)

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

            rev_growth  = None
            eps_uptrend = None
            div_yield   = 0.0

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

            try:
                qe = stock.quarterly_earnings
                if qe is not None and not qe.empty and "EPS" in qe.columns:
                    eps = qe["EPS"].dropna().tail(4)
                    if len(eps) >= 3:
                        diffs = eps.diff().dropna()
                        eps_uptrend = (diffs > 0).sum() >= len(diffs) * 0.5
            except Exception:
                pass

            try:
                dy = info.get("dividendYield")
                div_yield = round(dy * 100, 2) if dy else 0.0
            except Exception:
                pass

            avg_vol = df_raw["Volume"].tail(20).mean()

        df     = calc_indicators(df_raw)
        recent = df.dropna(subset=["MA25", "MA200"]).tail(5)
        ma25_up  = recent["MA25"].iloc[-1]  > recent["MA25"].iloc[0]  if len(recent) >= 2 else False
        ma200_up = recent["MA200"].iloc[-1] > recent["MA200"].iloc[0] if len(recent) >= 2 else False
        last     = df.dropna(subset=["MA25"]).iloc[-1]
        price    = last["Close"]
        deviation = (price - last["MA25"]) / last["MA25"] * 100

        bb_ok = True; bb_pos = 50.0
        if "BB_upper3" in df.columns:
            lbb   = df.dropna(subset=["BB_upper3"]).iloc[-1]
            bb_ok = price < lbb["BB_upper3"]
            bw    = lbb["BB_upper3"] - lbb["BB_lower3"]
            bb_pos = (price - lbb["BB_lower3"]) / bw * 100 if bw > 0 else 50.0

        closes = df["Close"].dropna()
        cup_detected = False; cup_high_val = None
        if len(closes) >= 125:
            r125 = closes.tail(125)
            cup_high_val = r125.max()
            after = r125[r125.index > r125.idxmax()]
            if len(after) >= 10:
                depth = (cup_high_val - after.min()) / cup_high_val * 100
                prox  = price / cup_high_val * 100
                cup_detected = (10 <= depth <= 40) and (prox >= 92)

        score = 0
        if ma25_up:              score += 10
        if ma200_up:             score += 10
        if abs(deviation) <= 10: score += 15
        if bb_ok:                score += 10
        if cup_detected:         score += 15
        if rev_growth is not None:
            score += 15 if rev_growth >= 25 else (10 if rev_growth >= 10 else 0)
        else:
            score += 7
        if eps_uptrend is True:   score += 15
        elif eps_uptrend is None: score += 7
        if avg_vol >= 50_000:     score += 10

        label = (
            "🟢 強い買いシグナル" if score >= 75 else
            "🟡 買い候補（要確認）" if score >= 55 else
            "🟠 待ち" if score >= 35 else "🔴 見送り"
        )

        latest = df["Close"].iloc[-1]
        chg    = (latest - df["Close"].iloc[-2]) / df["Close"].iloc[-2] * 100

        st.subheader(f"{name}（{ticker}）")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("現在値",     f"¥{latest:,.0f}")
        c2.metric("前日比",     f"{chg:+.2f}%")
        c3.metric("配当利回り", f"{div_yield:.2f}%")
        c4.metric("平均出来高", f"{avg_vol:,.0f}株")

        st.divider()
        st.subheader("🏆 総合投資スコア")
        st.progress(score / 100)
        st.markdown(f"### {score} / 100点　　{label}")

        with st.expander("スコア内訳を見る"):
            bd = {
                "MA25上向き":        10 if ma25_up else 0,
                "MA200上向き":       10 if ma200_up else 0,
                "25日乖離率10%以内": 15 if abs(deviation) <= 10 else 0,
                "BB+3σ未達":        10 if bb_ok else 0,
                "カップウィズハンドル": 15 if cup_detected else 0,
                "売上高成長率":      (15 if (rev_growth or 0) >= 25 else 10 if (rev_growth or 0) >= 10 else 7 if rev_growth is None else 0),
                "EPS増加基調":       (15 if eps_uptrend else 7 if eps_uptrend is None else 0),
                "出来高5万株以上":   10 if avg_vol >= 50_000 else 0,
            }
            st.dataframe(pd.DataFrame(list(bd.items()), columns=["項目", "得点"]),
                         use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("📊 判定結果")
        def ok(f):  return "✅ ○" if f else "❌ ×"
        def ok3(v): return "✅ ○" if v is True else "⬜ データなし" if v is None else "❌ ×"

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
                st.write(f"売上高成長率: {ok(rev_growth>=10)}（前年同期比 {rev_growth:+.1f}%）")
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
        if cup_high_val:
            fig.add_hline(y=cup_high_val, line_dash="dash", line_color="gold",
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
    st.caption("条件を設定して日本株300銘柄をスキャンします。結果はスコア順に表示されます。")

    with st.expander(f"📋 スキャン対象の{len(PRESET_TICKERS)}銘柄を確認する"):
        preset_df = pd.DataFrame(
            [{"銘柄コード": t.replace(".T",""), "銘柄名": n}
             for t, n in PRESET_TICKERS.items()])
        st.dataframe(preset_df, use_container_width=True, hide_index=True)
        st.markdown("**銘柄を追加する**（カンマ or 改行で区切る）")
        custom_input = st.text_area("追加銘柄コード",
            placeholder="例: 6532.T, 4385.T", height=70, key="custom_tickers")

    ticker_dict = dict(PRESET_TICKERS)
    if st.session_state.get("custom_tickers", "").strip():
        for t in st.session_state["custom_tickers"].replace("\n",",").split(","):
            t = t.strip().upper()
            if t:
                ticker_dict[t] = ticker_dict.get(t, "")

    st.caption(f"スキャン対象: **{len(ticker_dict)}銘柄** ／ 並列2スレッド・レート制限対策済み（目安: 約10〜15分）")

    st.divider()
    st.markdown("### ⚙️ スクリーニング条件")
    st.caption("💡 各指標の意味は「📖 指標の説明」タブで確認できます。")

    # ── 条件をすべて解除するボタン ──
    if st.button("🔄 条件をすべてリセット（全銘柄を表示）"):
        st.session_state["reset_all"] = True

    reset = st.session_state.get("reset_all", False)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**📈 テクニカル**")
        req_ma25  = st.checkbox("MA25が上向き",           value=not reset)
        req_ma200 = st.checkbox("MA200が上向き",          value=not reset)
        max_dev   = st.slider("25日乖離率の上限（%）",    0, 50, 0 if reset else 10)
        req_bb    = st.checkbox("BB+3σ未達",              value=not reset)
        req_cup   = st.checkbox("カップウィズハンドル検知", value=False)
    with c2:
        st.markdown("**💹 業績**")
        min_rev   = st.slider("売上高成長率の下限（%）",  -50, 50, -50 if reset else 10)
        req_eps   = st.checkbox("EPS増加基調",            value=not reset)
        min_vol   = st.number_input("最低出来高（株/日）", 0, 1_000_000, 0 if reset else 50_000, 10_000)
        st.markdown("**🏆 最低スコア**")
        min_score = st.slider("最低スコア（点）",          0, 100, 0 if reset else 30, 5)
    with c3:
        st.markdown("**💰 配当利回り**")
        use_div = st.checkbox("配当利回りでフィルタする",   value=False)
        min_div = st.slider("最低配当利回り（%）", 0.0, 10.0, 0.0, 0.1, disabled=not use_div)
        max_div = st.slider("最高配当利回り（%）", 0.0, 15.0, 10.0, 0.1, disabled=not use_div)

    if reset:
        st.session_state["reset_all"] = False

    st.divider()
    run_btn = st.button(f"🚀 {len(ticker_dict)}銘柄をスキャン開始",
                        type="primary", use_container_width=True)

    if run_btn:
        criteria = ScreenerCriteria(
            require_ma25_up=req_ma25,
            require_ma200_up=req_ma200,
            max_deviation_pct=float(max_dev if max_dev > 0 else 999),
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

        pb      = st.progress(0)
        st_txt  = st.empty()
        st_stat = st.empty()

        def on_progress(done, total, fetched, passed):
            pb.progress(int(done / total * 100))
            st_txt.caption(f"スキャン中... {done}/{total}銘柄")
            st_stat.caption(f"✅ データ取得成功: {fetched}社 　🎯 条件合格: {passed}社")

        with st.spinner("スクリーニング実行中..."):
            result_df, stats = run_screener(ticker_dict, criteria, progress_callback=on_progress)

        pb.empty(); st_txt.empty(); st_stat.empty()

        # 結果サマリー
        st.info(
            f"📊 スキャン完了 ── "
            f"対象: {stats['total']}銘柄 ／ "
            f"データ取得成功: {stats['fetched']}銘柄 ／ "
            f"条件合格: {stats['passed']}銘柄 ／ "
            f"取得失敗: {stats['failed']}銘柄"
        )

        if result_df.empty:
            st.warning("""
**条件に合う銘柄が見つかりませんでした。**

👉 以下をお試しください：
- 「条件をすべてリセット」ボタンを押してから再スキャン
- チェックボックスをすべて外す
- 「最低スコア」を 0 にする
- 「売上高成長率」を -50% まで下げる
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

            # CSVダウンロード
            csv = result_df.to_csv(index=False, encoding="utf-8-sig")
            st.download_button("📥 CSVでダウンロード", csv,
                               "screener_result.csv", "text/csv")

            # Gmail送信ボタン
            st.divider()
            st.markdown("### 📧 スクリーニング結果をメールで送る")
            g_addr = st.session_state.get("gmail_address", "")
            g_pass = st.session_state.get("gmail_app_password", "")
            g_to   = st.session_state.get("gmail_to", "")

            if g_addr and g_pass and g_to:
                mail_score = st.slider("メール送信するスコアの下限（点）", 0, 100, 50, 5,
                                       key="mail_score_filter")
                if st.button("📤 今すぐメールを送信", type="primary"):
                    ok_flag, msg = send_gmail(g_addr, g_pass, g_to, result_df, mail_score)
                    if ok_flag:
                        st.success(f"✅ {msg}")
                    else:
                        st.error(f"❌ {msg}")
            else:
                st.info("📧 メール送信するには「📧 Gmail通知設定」タブで情報を入力してください。")

        st.caption("⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。")


# ══════════════════════════════════════════════
# TAB 3：Gmail通知設定
# ══════════════════════════════════════════════
with tab3:
    st.subheader("📧 Gmail通知設定")
    st.markdown("""
スクリーニングで見つかった銘柄を**Gmailで自動通知**します。
**完全無料・送信数の制限なし**で利用できます。

設定に必要なのは以下の2つだけです。
- Gmailアドレス
- Googleアプリパスワード（通常のパスワードとは別の16文字のコード）
    """)

    with st.expander("📋 Googleアプリパスワードの取得方法（5分でできます）"):
        st.markdown("""
**手順：**

1. [https://myaccount.google.com](https://myaccount.google.com) を開く
2. 左メニューの「**セキュリティ**」をクリック
3. 「**2段階認証プロセス**」をオンにする（まだの場合）
4. 検索窓に「**アプリパスワード**」と入力して開く
5. アプリ名に「**投資ツール**」など任意の名前を入力
6. 「**作成**」をクリック → **16文字のパスワード**が表示される
7. そのパスワードをコピーして下の欄に貼り付ける

⚠️ アプリパスワードはこの画面でしか表示されません。必ずコピーしてください。
        """)

    st.divider()
    st.markdown("### メール設定を入力")

    col1, col2 = st.columns(2)
    with col1:
        gmail_input = st.text_input(
            "送信元Gmailアドレス",
            value=st.session_state.get("gmail_address", ""),
            placeholder="yourname@gmail.com",
        )
        gmail_to_input = st.text_input(
            "送信先メールアドレス",
            value=st.session_state.get("gmail_to", ""),
            placeholder="yourname@gmail.com（自分宛でもOK）",
        )
    with col2:
        app_pass_input = st.text_input(
            "Googleアプリパスワード（16文字）",
            value=st.session_state.get("gmail_app_password", ""),
            placeholder="xxxx xxxx xxxx xxxx",
            type="password",
            help="Googleアカウント → セキュリティ → アプリパスワード で取得",
        )

    if st.button("💾 保存する", type="primary", key="gmail_save"):
        if not gmail_input or "@" not in gmail_input:
            st.error("❌ 正しいGmailアドレスを入力してください。")
        elif not app_pass_input or len(app_pass_input.replace(" ", "")) < 16:
            st.error("❌ アプリパスワードは16文字です。Googleアカウントから取得してください。")
        elif not gmail_to_input or "@" not in gmail_to_input:
            st.error("❌ 送信先メールアドレスを入力してください。")
        else:
            st.session_state["gmail_address"]      = gmail_input
            st.session_state["gmail_app_password"] = app_pass_input.replace(" ", "")
            st.session_state["gmail_to"]           = gmail_to_input
            st.success("✅ 保存しました！スクリーナータブからメールを送信できます。")

    # テスト送信
    if st.session_state.get("gmail_address"):
        st.divider()
        st.markdown("### 📤 テスト送信")
        st.caption("設定が正しいか確認するためのテストメールを送ります。")
        if st.button("📧 テストメールを送る", key="gmail_test"):
            ok_flag, msg = send_test_gmail(
                st.session_state["gmail_address"],
                st.session_state["gmail_app_password"],
                st.session_state["gmail_to"],
            )
            if ok_flag:
                st.success(f"✅ テスト送信成功！メールを確認してください。")
            else:
                st.error(f"❌ 送信失敗：{msg}")

    st.divider()
    st.caption("""
⚠️ **セキュリティについて**
入力した情報はブラウザのセッションにのみ保存されます。
ページを閉じると消えますので、毎回入力が必要です。
アプリパスワードは通常のGoogleパスワードとは別物です。他人に見せないでください。
    """)


# ══════════════════════════════════════════════
# TAB 4：指標の説明
# ══════════════════════════════════════════════
with tab4:
    st.subheader("📖 各指標の意味と使い方")

    st.markdown("---")
    st.markdown("## 📈 テクニカル指標")

    st.markdown("### 1. MA25（25日移動平均線）が上向き")
    st.info("""
**移動平均線とは？**
過去N日間の終値の平均を線でつないだものです。

**25日線（約1ヶ月）が上向き**とは、短期的な株価トレンドが上昇していることを意味します。
下降トレンドの銘柄よりも、上昇トレンドに乗っている銘柄を選ぶほうが有利です。

📌 **判定基準**: 直近5日間でMA25が上昇していれば「○」
    """)

    st.markdown("### 2. MA200（200日移動平均線）が上向き")
    st.info("""
**200日線（約10ヶ月）が上向き**とは、長期的な株価トレンドが上昇していることを意味します。
機関投資家（大きな資金を動かすプロ）が最も重視する指標で、
200日線より上にある銘柄は「強い銘柄」とみなされます。

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

📌 **判定基準**: 乖離率が±10%以内なら「○"」
    """)

    st.markdown("### 4. ボリンジャーバンド +3σ未達")
    st.info("""
**ボリンジャーバンドとは？**
移動平均線を中心に、統計的なばらつき（σ＝シグマ）を上下に重ねたバンドです。

- **±2σ**: 株価がこの範囲内に収まる確率が約95%
- **±3σ**: 株価がこの範囲内に収まる確率が約99.7%

株価が**+3σに達している**場合、異常なほど買われすぎており、
反落リスクが非常に高い状態です。

📌 **判定基準**: 現在値がBB+3σより下なら「○」
    """)

    st.markdown("### 5. カップウィズハンドル")
    st.info("""
**カップウィズハンドルとは？**
アメリカの投資家ウィリアム・オニールが提唱した上昇前のチャートパターンです。

```
高値 ─────────────         ← ブレイクポイント
      ＼         ／
        ＼      ／  ← カップ（丸い底）
          ＼___／
              ← ハンドル（小さな調整）
```

高値をつけた後に10〜40%程度調整し、再び高値に近づく動きが出た銘柄は、
高値ブレイクから大きく上昇することが多いとされています。

📌 **判定基準**: 過去6ヶ月の調整幅10〜40% かつ現在値が高値の92%以上で「検知」
    """)

    st.markdown("---")
    st.markdown("## 💹 業績指標")

    st.markdown("### 6. 売上高成長率（前年同期比）")
    st.info("""
**売上高とは？**
会社が商品・サービスを販売して得た収入の合計です。

```
成長率 = (今期売上 − 前年同期売上) ÷ 前年同期売上 × 100
```

「成長株」として注目されるには、**最低10%、理想は25%以上**の成長が目安です。

📌 **配点**: 25%以上→15点 / 10%以上→10点 / 10%未満→0点
⚠️ yfinanceでデータが取れない銘柄は部分点（7点）が自動付与されます
    """)

    st.markdown("### 7. EPS（1株当たり利益）増加基調")
    st.info("""
**EPSとは？（Earnings Per Share）**
会社の純利益を発行済み株式数で割った数値です。

```
EPS = 純利益 ÷ 発行済み株式数
```

EPSが**連続して増加**していることは、会社の稼ぐ力が伸びていることを示します。

📌 **判定基準**: 直近3〜4四半期のうち半数以上で増加していれば「○」
⚠️ データが取れない銘柄は部分点（7点）が自動付与されます
    """)

    st.markdown("### 8. 出来高（5万株/日以上）")
    st.info("""
**出来高とは？**
1日に売買された株の総数です。

出来高が多いほど**機関投資家が参加できる流動性**があることを示します。
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
- **成長株を狙う場合**: 配当より株価上昇を重視するため0〜2%でも問題なし
- **利回りが高すぎる（8%超）**: 株価が大幅下落しているサインのこともあります
    """)

    st.markdown("---")
    st.markdown("## 🏆 総合スコアの見方")
    score_df = pd.DataFrame({
        "スコア範囲": ["75〜100点", "55〜74点", "35〜54点", "0〜34点"],
        "判定":       ["🟢 強い買いシグナル", "🟡 買い候補（要確認）", "🟠 待ち", "🔴 見送り"],
        "意味":       [
            "ほぼ全ての条件を満たす優良候補。積極的に調査する価値あり。",
            "多くの条件を満たす。チャートや業績を詳しく確認してから検討。",
            "条件を一部満たすが不十分。もう少し様子を見る。",
            "現時点では条件不足。ウォッチリストに入れて経過観察。",
        ]
    })
    st.dataframe(score_df, use_container_width=True, hide_index=True)
    st.caption("⚠️ 本ツールは情報提供を目的としており、投資助言ではありません。")
