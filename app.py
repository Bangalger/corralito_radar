import importlib
import os
import sys

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from dotenv import load_dotenv

# Recarga módulos locales en cada ejecución (Streamlit cachea imports entre reruns).
for _mod in (
    "src.text_utils",
    "src.news_quality",
    "src.nlp_engine",
    "src.serp_api_client",
    "src.mock_data_generator",
    "src.financial_api_client",
):
    if _mod in sys.modules:
        importlib.reload(sys.modules[_mod])

from src.mock_data_generator import get_mock_news
from src.financial_api_client import get_real_financial_data
from src.nlp_engine import RiskAnalyzer
from src.serp_api_client import fetch_current_news
from src.news_quality import normalize_news_items
from src.text_utils import as_text

# ================= Configuración Base =================
st.set_page_config(
    page_title="Radar de Riesgo Pa\u00eds", 
    layout="wide", 
    page_icon="\U0001F6A8",
    initial_sidebar_state="expanded"
)

# Estilos CSS Custom - UI Premium de Herramienta Financiera
st.markdown("""
<style>
.big-font { font-size: 2.5rem !important; font-weight: 700; color: #ffffff; }
.metric-box { 
    background-color: #1e1e2d; 
    border-left: 5px solid #E74C3C;
    padding: 20px; 
    border-radius: 8px; 
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    text-align: center; 
}
.metric-title { font-size: 1.1rem; color: #a1a5b7; text-transform: uppercase; letter-spacing: 1px;}
.metric-value { font-size: 2.2rem; font-weight: bold; color: #ffffff; margin-top: 10px; }
.highlight { color: #E74C3C; }
</style>
""", unsafe_allow_html=True)

load_dotenv()

DISCLAIMER = (
    "_Ejemplos ilustrativos de instrumentos; no constituyen asesoramiento financiero "
    "ni recomendación de inversión personalizada._"
)

REC_CRITICO = (
    "**ESTADO CRÍTICO (Riesgo > 85)**: Hay señales fuertes de pánico bancario, riesgo de default "
    "o restricciones severas (corralito).\n\n"
    "- 💵 **Bancarización Riesgosa:** Retirar depósitos en moneda extranjera del sistema financiero local.\n"
    "- 🔒 **Cripto / Cold Wallets:** Migrar liquidez a Stablecoins (USDT/USDC) en billeteras sin custodia.\n"
    "- 🛑 **Cero exposición soberana local:** Evitar bonos soberanos bajo legislación local y plazos fijos en pesos.\n"
    "- 🥫 **Bienes Reales:** Stockearse de insumos de su negocio y bienes durables no perecederos.\n"
    "- 📊 **Cobertura defensiva (ejemplos):** CEDEARs defensivos (KO, JNJ); ONs hard-dollar de exportadoras "
    "(YPF, Pampa, Telecom)."
)

REC_ALERTA = (
    "**ESTADO DE ALERTA (Riesgo 60 - 85)**: Turbulencia cambiaria aguda y alto riesgo inflacionario / cepo estricto.\n\n"
    "- 📉 **Cobertura Cambiaria:** Dolarizar excedentes vía Dólar MEP/CCL o Cripto.\n"
    "- 📊 **CEDEARs (ejemplos):** AAPL, MSFT, SPY para exposición dolarizada en bolsa local.\n"
    "- 💼 **ONs hard-dollar ley extranjera:** YPF, Pampa, Telecom (empresas exportadoras).\n"
    "- 📈 **Bonos soberanos hard-dollar ley NY (perfil agresivo):** GD30, GD35.\n"
    "- 🏃 **Pesos los mínimos:** Solo liquidez transaccional (ej. Fondos Money Market para pagos del mes)."
)

REC_ESTABLE = (
    "**ESTADO DE ESTABILIDAD (Riesgo < 60)**: Las métricas no reflejan una crisis terminal inminente a corto plazo.\n\n"
    "- 🔄 **Carry Trade en pesos (ejemplos):** LECAPs (letras capitalizables); bonos CER/BONCER (TX26, TZX26) "
    "si la tasa le gana a la devaluación esperada.\n"
    "- 📈 **Acciones locales Merval (ejemplos):** GGAL, YPFD, PAMP, BMA, ALUA, TXAR.\n"
    "- ⚖️ **Cartera Balanceada:** Estrategia mixta (dólares ~60% / bonos o activos en pesos ~40%)."
)


def _check_password():
    expected = os.getenv("APP_PASSWORD", "")
    if st.session_state.get("auth_ok"):
        return True
    gate = st.empty()
    with gate.container():
        pwd = st.text_input("Contraseña de acceso", type="password")
        if pwd and pwd == expected:
            st.session_state["auth_ok"] = True
            gate.empty()
            st.rerun()
        if pwd:
            st.error("Contraseña incorrecta.")
    return False


def main():
    st.markdown('<p class="big-font">\U0001F6A8 Corralito Radar / Alerta Temprana</p>', unsafe_allow_html=True)

    if not _check_password():
        st.stop()

    st.markdown("Monitor IA de Riesgo País: Analiza la **similitud discursiva** actual respecto a las grandes crisis argentinas (80s, 90s y 2001) usando **NLP y detección de anomalías** en series temporales.")
    
    # Sin @st.cache_resource: evita instancias viejas de RiskAnalyzer tras cambios de código.
    analyzer = RiskAnalyzer(historical_file='data/historical_events.json')
    
    # 1. Pipeline de Ingestión
    with st.spinner('Procesando datos del mercado e ingiriendo noticias...'):
        # Series de Tiempo (Precios reales/híbrido)
        df_fin, metadata = get_real_financial_data(90)
        
        # Ingesta Web API (multi-query + filtro amarillismo) o mock.
        current_news = fetch_current_news()
        using_mock = False
        no_recent = False
        if current_news is None:
            current_news = get_mock_news()
            using_mock = True
        elif len(current_news) == 0:
            no_recent = True
            current_news = []

        current_news = normalize_news_items(current_news)
        for item in current_news:
            item["text"] = as_text(item.get("text", ""))

        n_ok = sum(1 for n in current_news if n["status"] == "ok")
        n_reduced = sum(1 for n in current_news if n["status"] == "reduced")
        n_excluded = sum(1 for n in current_news if n["status"] == "excluded")
        n_offtopic = sum(1 for n in current_news if n["status"] == "offtopic")

    # Panel lateral de Configuración
    st.sidebar.image("https://cdn-icons-png.flaticon.com/512/3233/3233483.png", width=60)
    st.sidebar.header("Estado del Pipeline")
    if using_mock:
        status_icon_nlp = "⚠️ (Mock Data)"
    elif no_recent:
        status_icon_nlp = "⚠️ (Sin noticias recientes)"
    else:
        status_icon_nlp = "✅ (En Vivo)"
    st.sidebar.info(f"**Noticias (SerpAPI):** {status_icon_nlp}")
    st.sidebar.caption(
        f"Procesadas: {len(current_news)} · Peso completo: {n_ok} · "
        f"Reducidas: {n_reduced} · Excluidas: {n_excluded} · "
        f"Descartadas (loc): {n_offtopic}"
    )
    
    # Financial Status
    status_icon_dolar = "✅ (Real)" if metadata.get("dolar_real", False) else "⚠️ (Mock)"
    status_icon_series = "✅ (Series de Tiempo)" if metadata.get("bcra_real", False) else "⚠️ (Mock)"
    status_icon_rp = "✅ (Real)" if metadata.get("riesgo_pais_real", False) else "⚠️ (No disponible)"

    st.sidebar.info(f"**Dólar Blue:** {status_icon_dolar}")
    st.sidebar.info(f"**Reservas/Tasas:** {status_icon_series}")
    st.sidebar.info(f"**Riesgo País:** {status_icon_rp}")
    if metadata.get("riesgo_pais") is not None:
        st.sidebar.caption(f"EMBI+ actual: **{metadata['riesgo_pais']:.0f} bps**")
    if metadata.get("error_msg"):
        st.sidebar.caption(f"_{metadata['error_msg']}_")
        
    st.sidebar.divider()
    
    # Toggle de simulación de crisis extrema
    simular_crisis = st.sidebar.toggle("🚨 Simular Crisis Extrema", value=False, help="Fuerza los valores del modelo para previsualizar una alerta máxima.")
    
    st.sidebar.caption("Modelo NLP Activo: all-MiniLM-L6-v2")
    
    # 2. Pipeline Analítico
    nlp_results = analyzer.analyze_news(current_news)
    riesgo_pais = metadata.get("riesgo_pais")
    fin_score = analyzer.calculate_financial_score(df_fin, riesgo_pais=riesgo_pais)
    
    if "error" in nlp_results:
        st.error("Error en modulo de IA: " + nlp_results["error"] + ". (Asegurate de instalar los requirements).")
        st.stop()
        
    # Agrupamos resultados NLP
    max_nlp_sim = max(nlp_results.values())
    danger_epoch = max(nlp_results, key=nlp_results.get)
    
    # --- APLICAMOS SIMULACIÓN SI ESTÁ ACTIVA ---
    if simular_crisis:
        nlp_results = {'Años 80 (Hiperinflación)': 52.1, 'Años 90 (Plan Bonex)': 98.4, 'Año 2001 (Corralito)': 99.8}
        fin_score = 98.5
        max_nlp_sim = 99.8
        danger_epoch = 'Año 2001 (Corralito)'
        
        st.error("⚠️ **¡ALERTA MÁXIMA DETECTADA!** Los indicadores de similitud discursiva y anomalías de mercado han cruzado el umbral crítico del 95%. Se recomienda extrema precaución.", icon="🚨")
    
    # Cálculo General del Scoring de Riesgo IA
    # Ponderación elegida en la etapa de planeo
    total_risk = (max_nlp_sim * 0.45) + (fin_score * 0.55)
    
    # 3. Interfaz Visual (Dashboard Principal)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f'''
        <div class="metric-box">
            <div class="metric-title">Índice de Riesgo País (IA)</div>
            <div class="metric-value">{total_risk:.1f} / 100</div>
        </div>
        ''', unsafe_allow_html=True)
        st.progress(total_risk/100)
        
    with col2:
        rp_label = f"{riesgo_pais:.0f} bps" if riesgo_pais is not None else "N/D"
        st.markdown(f'''
        <div class="metric-box" style="border-left-color: #F39C12;">
            <div class="metric-title">Score Mercado (compuesto)</div>
            <div class="metric-value">{fin_score:.1f} / 100</div>
        </div>
        ''', unsafe_allow_html=True)
        st.caption(f"Riesgo País EMBI+: **{rp_label}**")

    with col3:
        st.markdown(f'''
        <div class="metric-box" style="border-left-color: #3498DB;">
            <div class="metric-title">Proyección de Época más Similar</div>
            <div class="metric-value" style="font-size: 1.8rem;">{danger_epoch}</div>
        </div>
        ''', unsafe_allow_html=True)

    st.divider()

    # --- SECCIÓN DE RECOMENDACIONES ACCIONABLES ---
    st.subheader("💡 Plan de Acción Recomendado")
    st.caption(DISCLAIMER)
    if total_risk >= 85:
        st.error(REC_CRITICO, icon="🚨")
    elif total_risk >= 60:
        st.warning(REC_ALERTA, icon="⚠️")
    else:
        st.success(REC_ESTABLE, icon="✅")

    st.divider()

    colA, colB = st.columns([6, 4])
    
    with colA:
        st.subheader("📊 Análisis Factorial: Series de Mercado (Últ. 90 ds)")
        st.caption("Evolución de brecha cambiaria, reservas y tasas con marcado de anomalías (Z-Score).")
        
        # Elegimos la columna de tasa disponible (BADLAR real o fallback mock).
        tasa_col = "Tasa BADLAR (%)" if "Tasa BADLAR (%)" in df_fin.columns else "Tasa Política M. (%)"
        y_cols = [c for c in ["Dólar Blue", tasa_col, "Reservas (M USD)"] if c in df_fin.columns]
        fig_line = px.line(
            df_fin, 
            x="Fecha", 
            y=y_cols,
            facet_col="variable", 
            facet_col_wrap=1, 
            height=600,
            template="plotly_dark"
        )
        fig_line.update_yaxes(matches=None) # Permitir diferentes escalas entre filas
        st.plotly_chart(fig_line, width="stretch")

    with colB:
        st.subheader("🧠 Radar Semántico (NLP)")
        st.caption("Comparación en espacio vectorial: Contexto actual vs Frases Históricas Míticas (Cine/Realidad).")
        
        # Gráfica de Barras Horizontal para NLP Matches
        df_sim = pd.DataFrame({"Período Histórico": list(nlp_results.keys()), "Concordancia (%)": list(nlp_results.values())})
        fig_bar = px.bar(
            df_sim, 
            y="Período Histórico", 
            x="Concordancia (%)", 
            color="Concordancia (%)", 
            color_continuous_scale="Reds",
            orientation='h',
            template="plotly_dark"
        )
        st.plotly_chart(fig_bar, width="stretch")
        
        st.subheader("📰 Ingesta de Noticias Procesadas Hoy")
        st.caption(
            "Búsquedas: crisis/cepo, corralito y default. "
            "Amarillismo alto reduce peso; muy alto excluye del score NLP."
        )
        with st.expander("Ver noticias ingresadas al motor de NLP", expanded=True):
            if no_recent:
                st.warning(
                    "No se encontraron noticias del último mes con las búsquedas actuales. "
                    "El score NLP se calcula sin contexto noticioso reciente."
                )
            elif using_mock:
                st.warning(
                    "SerpApi sin API KEY válida. Mostrando titulares mock "
                    "(incluye un ejemplo amarillista para probar el filtro)."
                )
            _status_labels = {
                "ok": ("✅ Peso completo", "normal"),
                "reduced": ("⚠️ Peso reducido", "warning"),
                "excluded": ("🚫 Excluida del NLP", "error"),
                "offtopic": ("📍 Descartada (localidad Córdoba)", "error"),
            }
            for item in current_news:
                label, tone = _status_labels.get(item["status"], ("?", "normal"))
                query_tag = f" · búsqueda: _{item['query']}_" if item.get("query") else ""
                date_tag = f" · fecha: _{item['date']}_" if item.get("date") else ""
                source = item.get("source", "")
                link = item.get("link", "")
                if source and link:
                    source_tag = f" · fuente: [{source}]({link})"
                elif source:
                    source_tag = f" · fuente: _{source}_"
                else:
                    source_tag = ""
                st.markdown(
                    f"- {label} (amarillismo {item['sensationalism']:.0%}, peso {item['weight']:.0%})"
                    f"{query_tag}{date_tag}{source_tag}\n  - *\"{item['text']}\"*"
                )

if __name__ == "__main__":
    main()
