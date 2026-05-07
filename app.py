import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github
from logic_programador import (
    generar_malla_base, 
    aplicar_estilos, 
    obtener_horario, 
    es_cambio_saludable,
    conectar_github
)

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Logic", layout="wide")

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
        repo.update_file(nombre, "Actualización Malla", output.getvalue(), contents.sha)
    except:
        repo.create_file(nombre, "Carga Inicial", output.getvalue())

def renderizar_malla_ordenada(df):
    """Asegura que las columnas aparezcan por fecha y no alfabéticamente."""
    if df.empty: return
    df = df.sort_values("Fecha_Raw")
    orden_fechas = df["Fecha_Col"].unique()
    
    es_persona = "Nombre" in df.columns
    pivot_idx = ["Nombre", "Grupo"] if es_persona else "Grupo"
    
    matriz = df.pivot_table(index=pivot_idx, columns="Fecha_Col", values="Turno", aggfunc='first')
    # RE-ORDENAR COLUMNAS PARA EVITAR ALFABÉTICO
    matriz = matriz[orden_fechas]
    st.dataframe(aplicar_estilos(matriz), use_container_width=True)

# --- MÓDULOS ---
def modulo_programacion():
    st.header("📅 Programación y Auditoría")
    repo = conectar_github()
    
    with st.expander("⚙️ Herramientas de Generación", expanded=True):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Fecha Inicio", datetime(2026, 7, 1))
        f_fin = c2.date_input("Fecha Fin", datetime(2026, 7, 31))
        if st.button("🚀 Calcular y Guardar Nueva Malla"):
            df_n = generar_malla_base(f_ini, f_fin, repo)
            guardar_excel(df_n, "malla_historica.xlsx")
            st.rerun()

    df_m = cargar_excel("malla_historica.xlsx")
    if not df_m.empty:
        df_view = df_m[(df_m['Fecha_Raw'] >= pd.to_datetime(f_ini)) & (df_m['Fecha_Raw'] <= pd.to_datetime(f_fin))]
        
        # MÉTRICAS
        st.subheader("📊 Auditoría de Grupos")
        m_cols = st.columns(4)
        for i, g in enumerate(["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]):
            ult_reg = df_view[df_view["Grupo"] == g]
            deuda = ult_reg.iloc[-1]["Deuda_Compensatorio"] if not ult_reg.empty else 0
            m_cols[i].metric(g, f"{deuda} días", delta="Compensatorio")

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
        else: st.success("✅ Rotación segura para la salud.")

        st.subheader("Vista por Grupos")
        renderizar_malla_ordenada(df_view)

def modulo_detallado():
    st.header("👤 Detallado por Técnico")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    if not df_m.empty and not df_e.empty:
        df_det = df_e.merge(df_m, on="Grupo")
        renderizar_malla_ordenada(df_det)
    else:
        st.warning("Se requiere cargar 'empleados.xlsx' en GitHub.")

# --- MENÚ ---
menu = st.sidebar.radio("Navegación", ["Programación", "Detallado"])
if menu == "Programación": modulo_programacion()
else: modulo_detallado()
