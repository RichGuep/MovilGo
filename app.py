import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github
from logic_programador import (
    generar_malla_base, aplicar_estilos, obtener_horario, 
    es_cambio_saludable, conectar_github
)

# --- CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="MovilGo Logic", layout="wide")

PRIMARY_COLOR = "#1E3D59"
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGOS_EMPRESAS = {
    "Greenmóvil": f"{URL_BASE}logo_empresa_1.png",
    "Cable Móvil": f"{URL_BASE}logo_empresa_2.png",
    "BogotáMóvil": f"{URL_BASE}logo_empresa_3.png"
}

st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .metric-card {{ background: white; padding: 15px; border-radius: 10px; border-left: 5px solid {PRIMARY_COLOR}; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 10px; }}
    </style>
    """, unsafe_allow_html=True)

# --- FUNCIONES DE DATOS ---
def cargar_excel(nombre):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        content = repo.get_contents(nombre)
        df = pd.read_excel(io.BytesIO(content.decoded_content))
        if 'Fecha_Raw' in df.columns: df['Fecha_Raw'] = pd.to_datetime(df['Fecha_Raw'])
        return df
    except: return pd.DataFrame()

def guardar_excel(df, nombre):
    repo = conectar_github()
    if not repo: return
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False)
    try:
        contents = repo.get_contents(nombre)
        repo.update_file(nombre, "Update Malla", output.getvalue(), contents.sha)
    except: repo.create_file(nombre, "Init Malla", output.getvalue())

def renderizar_malla_ordenada(df):
    if df.empty: return
    # TRUCO: Ordenar por fecha real y capturar los nombres de los días para las columnas
    df = df.sort_values("Fecha_Raw")
    orden_columnas = df["Fecha_Col"].unique()
    
    es_persona = "Nombre" in df.columns
    pivot_idx = ["Nombre", "Grupo"] if es_persona else "Grupo"
    
    matriz = df.pivot_table(index=pivot_idx, columns="Fecha_Col", values="Turno", aggfunc='first')
    # Forzar el orden cronológico capturado arriba
    matriz = matriz[orden_columnas]
    st.dataframe(aplicar_estilos(matriz), use_container_width=True)

# --- MÓDULOS ---
def modulo_programacion():
    st.header("📅 Programación Maestra y Auditoría")
    repo = conectar_github()
    
    with st.expander("🚀 Generar Nuevo Periodo", expanded=True):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Inicio", datetime(2026, 7, 1))
        f_fin = c2.date_input("Fin", datetime(2026, 7, 31))
        if st.button("🚀 Calcular Nueva Rotación"):
            df_res = generar_malla_base(f_ini, f_fin, repo)
            guardar_excel(df_res, "malla_historica.xlsx")
            st.rerun()

    df_m = cargar_excel("malla_historica.xlsx")
    if not df_m.empty:
        df_view = df_m[(df_m['Fecha_Raw'] >= pd.to_datetime(f_ini)) & (df_m['Fecha_Raw'] <= pd.to_datetime(f_fin))]
        
        # MÉTRICAS DE DEUDA
        st.subheader("📊 Deuda de Compensatorios")
        m_cols = st.columns(4)
        for i, g in enumerate(["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]):
            ult_reg = df_view[df_view["Grupo"] == g]
            deuda = ult_reg.iloc[-1]["Deuda_Compensatorio"] if not ult_reg.empty else 0
            m_cols[i].metric(g, f"{deuda} días")

        # ALERTAS DE SALUD
        st.subheader("⚠️ Alertas de Salud Laboral")
        alertas = []
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            data = df_m[df_m["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
            for i in range(1, len(data)):
                if data[i]['Fecha_Raw'] >= pd.to_datetime(f_ini):
                    if not es_cambio_saludable(data[i-1]['Turno'], data[i]['Turno']):
                        alertas.append(f"**{g}**: Salto prohibido {data[i-1]['Turno']} -> {data[i]['Turno']} el {data[i]['Fecha_Col']}")
        if alertas:
            for a in alertas: st.error(a)
        else: st.success("✅ Rotación saludable.")

        st.subheader("Vista por Grupos")
        renderizar_malla_ordenada(df_view)

def modulo_detallado():
    st.header("📋 Detallado por Técnico")
    df_m, df_e = cargar_excel("malla_historica.xlsx"), cargar_excel("empleados.xlsx")
    if not df_m.empty and not df_e.empty:
        df_det = df_e.merge(df_m, on="Grupo")
        renderizar_malla_ordenada(df_det)
    else: st.info("Sube 'empleados.xlsx' para ver nombres individuales.")

# --- NAVEGACIÓN ---
if 'empresa' not in st.session_state: st.session_state.empresa = None

if st.session_state.empresa is None:
    st.image(LOGO_APP, width=200)
    st.subheader("Seleccione Operación")
    c1, c2, c3 = st.columns(3)
    for i, emp in enumerate(LOGOS_EMPRESAS.keys()):
        with [c1, c2, c3][i]:
            st.image(LOGOS_EMPRESAS[emp], width=120)
            if st.button(f"Entrar {emp}"): 
                st.session_state.empresa = emp
                st.rerun()
else:
    with st.sidebar:
        st.image(LOGOS_EMPRESAS[st.session_state.empresa], width=150)
        menu = st.radio("MENÚ", ["📅 Programación", "📋 Detallado", "👥 Personal"])
        if st.button("🚪 Salir"): st.session_state.empresa = None; st.rerun()

    if menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado": modulo_detallado()
    elif menu == "👥 Personal":
        df_emp = cargar_excel("empleados.xlsx")
        df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
        if st.button("💾 Guardar"): guardar_excel(df_edit, "empleados.xlsx")
