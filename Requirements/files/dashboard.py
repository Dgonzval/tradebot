import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

# ============= CONFIG =============
st.set_page_config(
    page_title="Trading Bot Dashboard",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded",
)

import os
API_BASE = os.getenv("API_BASE_URL", "http://api:8000")

# ============= ESTILOS =============
st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 20px;
        border-left: 4px solid #7c3aed;
    }
    .positive { color: #22c55e; font-weight: bold; }
    .negative { color: #ef4444; font-weight: bold; }
    .neutral  { color: #94a3b8; }
    .section-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #e2e8f0;
        margin-bottom: 0.5rem;
    }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; }
    div[data-testid="stMetricDelta"] { font-size: 0.9rem; }
</style>
""", unsafe_allow_html=True)

# ============= HELPERS =============
@st.cache_data(ttl=30)
def get_positions():
    try:
        return requests.get(f"{API_BASE}/positions", timeout=5).json()
    except:
        return {}

@st.cache_data(ttl=30)
def get_portfolio_value():
    try:
        return requests.get(f"{API_BASE}/portfolio-value", timeout=5).json()
    except:
        return {"total_usd": 0}

@st.cache_data(ttl=60)
def get_news():
    try:
        return requests.get(f"{API_BASE}/news", timeout=10).json()
    except:
        return {"articles": [], "count": 0}

@st.cache_data(ttl=30)
def get_signals():
    try:
        return requests.get(f"{API_BASE}/signals?limit=20", timeout=5).json()
    except:
        return []

@st.cache_data(ttl=300)
def get_price_history(symbol: str, period: str = "1mo"):
    try:
        from yf_session import get_history
        period_days = {"1mo": 30, "3mo": 90, "6mo": 180, "1y": 365, "5d": 5, "1d": 1}.get(period, 30)
        df = get_history(symbol, days=period_days)
        if df is not None and not df.empty:
            df.index = pd.to_datetime(df.index)
            return df
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=300)
def get_indicators_cached(symbol: str):
    try:
        from technical_indicators import get_indicators
        return get_indicators(symbol)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"get_indicators error for {symbol}: {e}")
        return {}

def api_healthy():
    try:
        r = requests.get(f"{API_BASE}/health", timeout=3).json()
        return r.get("status") == "running", r.get("redis", "unknown")
    except:
        return False, "disconnected"

# ============= SIDEBAR =============
with st.sidebar:
    st.markdown("## Trading Bot IA")
    st.markdown("---")

    api_ok, redis_status = api_healthy()
    st.markdown(f"**API:** {'🟢 Online' if api_ok else '🔴 Offline'}")
    st.markdown(f"**Redis:** {'🟢 Connected' if 'connected' in redis_status else '🔴 ' + redis_status}")
    st.markdown("---")

    period = st.selectbox("Periodo graficos", ["5d", "1mo", "3mo", "6mo", "1y"], index=1)
    chart_type = st.radio("Tipo de grafico", ["Velas", "Linea"], index=0)
    st.markdown("---")

    if st.button("Actualizar datos", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    auto_refresh = st.toggle("Auto-refresh (30s)", value=False)
    if auto_refresh:
        import time
        time.sleep(30)
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("**Accesos rapidos**")
    st.markdown("- [API Docs](http://localhost:8000/docs)")
    st.markdown("- [pgAdmin](http://localhost:5050)")
    st.caption(f"Actualizado: {datetime.now().strftime('%H:%M:%S')}")

# ============= MAIN =============
st.title("Trading Bot Dashboard")

tabs = st.tabs(["Resumen", "Posiciones", "Graficos", "Noticias", "Senales"])

# ============= TAB 1: RESUMEN =============
with tabs[0]:
    positions = get_positions()
    portfolio = get_portfolio_value()

    # KPIs principales
    col1, col2, col3, col4 = st.columns(4)

    total_invested = sum(
        p["quantity"] * p["entry_price"] for p in positions.values()
    )
    total_current = portfolio["total_usd"]
    total_pnl = total_current - total_invested
    total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0

    with col1:
        st.metric("Valor Total", f"${total_current:,.2f}", f"{total_pnl_pct:+.2f}%")
    with col2:
        st.metric("Capital Invertido", f"${total_invested:,.2f}")
    with col3:
        st.metric("P&L Total", f"${total_pnl:+,.2f}", f"{'Ganancia' if total_pnl >= 0 else 'Perdida'}")
    with col4:
        signals = get_signals()
        last_signal = signals[0] if signals else None
        if last_signal:
            st.metric(
                "Ultima Senal",
                f"{last_signal['action']} {last_signal['symbol']}",
                last_signal["created_at"][:10],
            )
        else:
            st.metric("Ultima Senal", "Sin senales", "")

    st.markdown("---")
    col_left, col_right = st.columns([1, 1])

    # Gráfico de distribución de cartera
    with col_left:
        st.markdown("#### Distribucion de Cartera")
        if positions:
            labels, values, colors_list = [], [], []
            palette = ["#7c3aed", "#2563eb", "#059669", "#d97706", "#dc2626"]
            for i, (sym, pos) in enumerate(positions.items()):
                val = (pos["current_price"] or pos["entry_price"]) * pos["quantity"]
                labels.append(sym)
                values.append(val)
                colors_list.append(palette[i % len(palette)])

            fig = go.Figure(go.Pie(
                labels=labels, values=values,
                hole=0.55,
                marker=dict(colors=colors_list, line=dict(color="#0f172a", width=2)),
                textinfo="label+percent",
                textfont=dict(size=13),
            ))
            fig.update_layout(
                showlegend=False,
                margin=dict(t=20, b=20, l=20, r=20),
                height=300,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig, use_container_width=True)

    # Gráfico P&L por activo
    with col_right:
        st.markdown("#### P&L por Activo (%)")
        if positions:
            syms = list(positions.keys())
            pnls = [positions[s]["pnl_percent"] for s in syms]
            bar_colors = ["#22c55e" if p >= 0 else "#ef4444" for p in pnls]

            fig2 = go.Figure(go.Bar(
                x=syms, y=pnls,
                marker_color=bar_colors,
                text=[f"{p:+.2f}%" for p in pnls],
                textposition="outside",
            ))
            fig2.update_layout(
                yaxis_title="P&L %",
                yaxis=dict(zeroline=True, zerolinecolor="#475569"),
                margin=dict(t=30, b=20, l=20, r=20),
                height=300,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
            )
            st.plotly_chart(fig2, use_container_width=True)

    # Ultimas noticias resumen
    st.markdown("#### Ultimas Noticias")
    news_data = get_news()
    articles = news_data.get("articles", [])[:4]
    if articles:
        news_cols = st.columns(2)
        for i, art in enumerate(articles):
            with news_cols[i % 2]:
                st.markdown(f"""
                <div style="background:#1e293b;padding:12px;border-radius:8px;margin-bottom:8px;border-left:3px solid #7c3aed">
                    <div style="font-size:0.75rem;color:#94a3b8">{art['symbol']} · {art['source']} · {art['published_at'][:10]}</div>
                    <div style="font-size:0.9rem;color:#e2e8f0;margin-top:4px">{art['title'][:100]}</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Sin noticias en cache. Espera el siguiente ciclo de actualización.")

# ============= TAB 2: POSICIONES =============
with tabs[1]:
    positions = get_positions()
    st.markdown("#### Posiciones Actuales")

    if positions:
        rows = []
        for sym, p in positions.items():
            cp = p["current_price"]
            ep = p["entry_price"]
            qty = p["quantity"]
            pnl_pct = p["pnl_percent"]
            current_val = (cp or ep) * qty
            entry_val = ep * qty
            rows.append({
                "Simbolo": sym,
                "Cantidad": qty,
                "Precio Entrada": f"${ep:,.2f}",
                "Precio Actual": f"${cp:,.2f}" if cp else "N/A",
                "Valor Entrada": f"${entry_val:,.2f}",
                "Valor Actual": f"${current_val:,.2f}",
                "P&L %": pnl_pct,
                "P&L USD": f"${(current_val - entry_val):+,.2f}",
                "Actualizado": p["last_updated"][:16].replace("T", " ") if p["last_updated"] else "N/A",
            })

        df = pd.DataFrame(rows)

        def color_pnl(val):
            if isinstance(val, float):
                color = "#22c55e" if val >= 0 else "#ef4444"
                return f"color: {color}; font-weight: bold"
            return ""

        styled = df.style.applymap(color_pnl, subset=["P&L %"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

        # Totales
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        total_entry = sum(p["entry_price"] * p["quantity"] for p in positions.values())
        total_now = sum((p["current_price"] or p["entry_price"]) * p["quantity"] for p in positions.values())
        with col1:
            st.metric("Total Invertido", f"${total_entry:,.2f}")
        with col2:
            st.metric("Valor Actual", f"${total_now:,.2f}")
        with col3:
            diff = total_now - total_entry
            st.metric("P&L Total", f"${diff:+,.2f}", f"{diff/total_entry*100:+.2f}%")
    else:
        st.warning("Sin posiciones. La API puede estar offline.")

# ============= TAB 3: GRAFICOS =============
with tabs[2]:
    positions = get_positions()
    symbols = list(positions.keys()) if positions else ["BTC", "ETH"]

    selected = st.selectbox("Activo", symbols)
    st.markdown(f"#### {selected} — Historico de precios ({period})")

    hist = get_price_history(selected, period)

    if not hist.empty:
        if chart_type == "Velas":
            fig = go.Figure(go.Candlestick(
                x=hist.index,
                open=hist["Open"], high=hist["High"],
                low=hist["Low"], close=hist["Close"],
                increasing_line_color="#22c55e",
                decreasing_line_color="#ef4444",
            ))
        else:
            fig = go.Figure(go.Scatter(
                x=hist.index, y=hist["Close"],
                mode="lines",
                line=dict(color="#7c3aed", width=2),
                fill="tozeroy",
                fillcolor="rgba(124,58,237,0.1)",
            ))

        # Línea de precio de entrada
        if selected in positions and positions[selected]["entry_price"]:
            ep = positions[selected]["entry_price"]
            fig.add_hline(
                y=ep, line_dash="dash",
                line_color="#f59e0b", line_width=1.5,
                annotation_text=f"Entrada ${ep:,.0f}",
                annotation_position="bottom right",
            )

        fig.update_layout(
            height=450,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(15,23,42,1)",
            xaxis=dict(gridcolor="#1e293b", showgrid=True),
            yaxis=dict(gridcolor="#1e293b", showgrid=True, title="Precio USD"),
            font=dict(color="#e2e8f0"),
            xaxis_rangeslider_visible=False,
            margin=dict(t=30, b=20, l=20, r=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        last_close = hist["Close"].iloc[-1]
        first_close = hist["Close"].iloc[0]
        change_pct = (last_close - first_close) / first_close * 100

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Precio actual", f"${last_close:,.2f}")
        c2.metric("Maximo periodo", f"${hist['High'].max():,.2f}")
        c3.metric("Minimo periodo", f"${hist['Low'].min():,.2f}")
        c4.metric(f"Cambio {period}", f"{change_pct:+.2f}%")

        # Indicadores tecnicos
        st.markdown("---")
        col_h, col_btn = st.columns([4, 1])
        col_h.markdown("#### Indicadores Tecnicos")
        if col_btn.button("Refrescar", key="refresh_ind"):
            get_indicators_cached.clear()
            st.rerun()
        ind = get_indicators_cached(selected)
        if ind:
            osc = ind.get("osciladores", {})
            mm = ind.get("medias_moviles", {})
            vol = ind.get("volumen", {})
            bb = ind.get("bollinger_bands", {})
            macd_data = ind.get("MACD", {})
            atr_data = ind.get("volatilidad", {})
            niveles = ind.get("niveles_clave", {})
            momentum = ind.get("momentum_pct", {})
            stoch = osc.get("Estocastico", {})

            col1, col2, col3, col4, col5 = st.columns(5)
            rsi = osc.get("RSI_14", {})
            rsi_val = rsi.get("valor", 0)
            col1.metric("RSI 14", rsi_val, rsi.get("zona", ""))

            col2.metric("MACD", macd_data.get("linea", "N/A"), macd_data.get("direccion", ""))

            col3.metric("SMA 20", f"${mm.get('SMA20', 0):,.2f}",
                       "Precio arriba" if mm.get("precio_sobre_SMA20") else "Precio abajo")
            col4.metric("SMA 50", f"${mm.get('SMA50', 0):,.2f}" if mm.get("SMA50") else "N/A",
                       "Precio arriba" if mm.get("precio_sobre_SMA50") else "Precio abajo")

            col5.metric("Volumen", vol.get("nivel", "N/A"), f"x{vol.get('ratio_vs_media20', 1):.1f} media")

            col6, col7, col8, col9, col10 = st.columns(5)
            col6.metric("BB Superior", f"${bb.get('superior', 0):,.2f}")
            col7.metric("BB Inferior", f"${bb.get('inferior', 0):,.2f}")
            col7.caption(bb.get("zona", ""))

            col8.metric("Estocastico K", stoch.get("K", "N/A"), stoch.get("cruce", ""))
            atr_val = atr_data.get("ATR_14", 0)
            col9.metric("ATR 14", f"${atr_val:,.2f}", f"{atr_data.get('ATR_pct_precio', 0):.2f}% precio")

            pct_max = niveles.get("pct_desde_maximo", 0)
            high_p = niveles.get("maximo_periodo", 0)
            col10.metric("Desde maximo", f"{pct_max:+.1f}%", f"Max: ${high_p:,.0f}")

            # Fila 3: Williams R, CCI, OBV, VWAP, EMA9/21
            st.markdown("")
            col11, col12, col13, col14, col15 = st.columns(5)
            wr = osc.get("Williams_R", {})
            col11.metric("Williams %R", wr.get("valor", "N/A"), wr.get("zona", ""))

            cci = osc.get("CCI_20", {})
            col12.metric("CCI 20", cci.get("valor", "N/A"), cci.get("zona", ""))

            col13.metric("OBV Tendencia", vol.get("OBV_tendencia", "N/A"))

            vwap = mm.get("VWAP", 0)
            col14.metric("VWAP", f"${vwap:,.2f}" if vwap else "N/A",
                        "Precio arriba" if mm.get("precio_sobre_VWAP") else "Precio abajo")

            ema_cross = "EMA9 > EMA21" if mm.get("EMA9_sobre_EMA21") else "EMA9 < EMA21"
            col15.metric("EMA 9/21", f"${mm.get('EMA9', 0):,.2f}", ema_cross)

            st.caption(f"Tendencia general: **{ind.get('tendencia_general', 'N/A')}** | "
                      f"Cambio 7d: {momentum.get('7d', 0):+.2f}% | "
                      f"Cambio 30d: {momentum.get('30d', 0):+.2f}%")

            # Fundamentales (solo stocks)
            fundamentals = ind.get("fundamentales")
            if fundamentals:
                st.markdown("---")
                st.markdown("#### Datos Fundamentales")
                fc1, fc2, fc3, fc4, fc5 = st.columns(5)
                fc1.metric("P/E Ratio", fundamentals.get("pe_ratio", "N/A"))
                fc2.metric("P/E Forward", fundamentals.get("pe_forward", "N/A"))
                fc3.metric("Market Cap", f"${fundamentals.get('market_cap_B', 0):.1f}B" if fundamentals.get('market_cap_B') else "N/A")
                fc4.metric("ROE %", f"{fundamentals.get('roe_pct', 0):.1f}%" if fundamentals.get('roe_pct') else "N/A")
                fc5.metric("Beta", fundamentals.get("beta", "N/A"))

                fc6, fc7, fc8, fc9, fc10 = st.columns(5)
                fc6.metric("Margen %", f"{fundamentals.get('profit_margin_pct', 0):.1f}%" if fundamentals.get('profit_margin_pct') else "N/A")
                fc7.metric("Crec. Revenue", f"{fundamentals.get('revenue_growth_pct', 0):+.1f}%" if fundamentals.get('revenue_growth_pct') else "N/A")
                fc8.metric("Dividendo %", f"{fundamentals.get('dividend_yield_pct', 0):.2f}%" if fundamentals.get('dividend_yield_pct') else "N/A")
                fc9.metric("Precio Objetivo", f"${fundamentals.get('precio_objetivo_analistas', 0):,.2f}" if fundamentals.get('precio_objetivo_analistas') else "N/A")
                fc10.metric("Analistas", str(fundamentals.get("recomendacion_analistas", "N/A")).upper())

            # Opciones (solo stocks)
            options = ind.get("opciones_sentimiento")
            if options:
                st.markdown("---")
                st.markdown("#### Sentimiento Opciones")
                oc1, oc2, oc3 = st.columns(3)
                oc1.metric("Put/Call Ratio", options.get("put_call_ratio", "N/A"))
                oc2.metric("IV Promedio %", f"{options.get('iv_promedio_pct', 0):.1f}%")
                oc3.metric("Sesgo", options.get("sesgo", "N/A"))
    else:
        st.warning(f"Calculando indicadores para {selected}... Pulsa **Refrescar** o espera 5 minutos.")

# ============= TAB 4: NOTICIAS =============
with tabs[3]:
    news_data = get_news()
    articles = news_data.get("articles", [])

    st.markdown(f"#### Noticias del mercado — {news_data.get('count', 0)} articulos")

    if articles:
        filter_sym = st.multiselect(
            "Filtrar por activo",
            options=list(set(a["symbol"] for a in articles)),
            default=[],
        )
        filtered = [a for a in articles if not filter_sym or a["symbol"] in filter_sym]

        for art in filtered:
            with st.container():
                col_badge, col_content = st.columns([1, 9])
                with col_badge:
                    st.markdown(f"""
                    <div style="background:#7c3aed;color:white;padding:4px 8px;border-radius:6px;
                                text-align:center;font-size:0.8rem;font-weight:bold;margin-top:4px">
                        {art['symbol']}
                    </div>""", unsafe_allow_html=True)
                with col_content:
                    st.markdown(f"**[{art['title']}]({art['url']})**")
                    st.caption(f"{art['source']} · {art['published_at'][:16].replace('T', ' ')}")
                st.divider()
    else:
        st.info("Sin noticias en cache. Espera el siguiente ciclo o fuerza actualización.")

# ============= TAB 5: SENALES =============
with tabs[4]:
    signals = get_signals()
    st.markdown("#### Senales TradingView")

    if signals:
        buys = sum(1 for s in signals if s["action"] == "BUY")
        sells = sum(1 for s in signals if s["action"] == "SELL")

        c1, c2, c3 = st.columns(3)
        c1.metric("Total senales", len(signals))
        c2.metric("BUY", buys, delta=None)
        c3.metric("SELL", sells, delta=None)

        st.markdown("---")

        for s in signals:
            is_buy = s["action"] == "BUY"
            color = "#22c55e" if is_buy else "#ef4444"
            border = "#166534" if is_buy else "#991b1b"
            price_str = f"${s['price']:,.2f}" if s["price"] else "N/A"

            st.markdown(f"""
            <div style="background:#1e293b;border-left:4px solid {color};
                        border-radius:8px;padding:12px 16px;margin-bottom:8px;
                        display:flex;justify-content:space-between;align-items:center">
                <div>
                    <span style="color:{color};font-weight:bold;font-size:1rem">
                        {s['action']} {s['symbol']}
                    </span>
                    <span style="color:#94a3b8;margin-left:12px;font-size:0.85rem">
                        via {s['source']}
                    </span>
                </div>
                <div style="text-align:right">
                    <div style="color:#e2e8f0;font-weight:bold">{price_str}</div>
                    <div style="color:#94a3b8;font-size:0.8rem">
                        {s['created_at'][:16].replace('T', ' ')}
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Gráfico de senales en el tiempo
        if len(signals) > 1:
            st.markdown("#### Distribucion de senales")
            df_sig = pd.DataFrame(signals)
            df_sig["created_at"] = pd.to_datetime(df_sig["created_at"])
            counts = df_sig.groupby("action").size().reset_index(name="count")
            fig = px.pie(
                counts, names="action", values="count",
                color="action",
                color_discrete_map={"BUY": "#22c55e", "SELL": "#ef4444"},
                hole=0.4,
            )
            fig.update_layout(
                height=280,
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e2e8f0"),
                margin=dict(t=20, b=20, l=20, r=20),
            )
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin senales registradas. Envia un webhook de TradingView a POST /tradingview-webhook")
        st.code("""{
  "ticker": "BTCUSD",
  "action": "buy",
  "close": 65000
}""", language="json")
