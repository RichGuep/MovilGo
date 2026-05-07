import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github
from logic_programador import (
    generar_malla_base, aplicar_estilos, es_cambio_saludable, 
    conectar_github, OPCIONES_TURNOS
)

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="MovilGo Pro", layout="wide")

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
        repo.update_file(nombre, "Update", output.getvalue(), contents.sha)
    except: repo.create_file(nombre, "Init", output.getvalue())

# --- FUNCIÓN POP-UP PARA EDICIÓN ---
@st.dialog("Editar Turno Manual")
def editar_turno_popup(df_original, grupo, fecha_col):
    st.write(f"Modificando: **{grupo}** para el día **{fecha_col}**")
    nuevo_turno = st.selectbox("Seleccione el nuevo turno:", OPCIONES_TURNOS)
    
    if st.button("Confirmar Cambio"):
        # Actualizar el DataFrame original
        mask = (df_original['Grupo'] == grupo) & (df_original['Fecha_Col'] == fecha_col)
        df_original.loc[mask, 'Turno'] = nuevo_turno
        guardar_excel(df_original, "malla_historica.xlsx")
        st.success("Turno actualizado correctamente")
        st.rerun()

# --- COMPONENTE DE MALLA ORDENADA ---
def renderizar_malla_pro(df):
    if df.empty: return
    df = df.sort_values("Fecha_Raw")
    orden_cols = df["Fecha_Col"].unique()
    
    # Vista por Grupos
    matriz = df.pivot_table(index="Grupo", columns="Fecha_Col", values="Turno", aggfunc='first')[orden_cols]
    st.subheader("📊 Malla por Grupos")
    st.dataframe(aplicar_estilos(matriz), use_container_width=True)
    
    # Selector para el Pop-up
    st.divider()
    st.subheader("✏️ Editor Rápido")
    col_edit1, col_edit2, col_edit3 = st.columns([1, 1, 1])
    sel_g = col_edit1.selectbox("Grupo a editar:", df["Grupo"].unique())
    sel_f = col_edit2.selectbox("Día a editar:", orden_cols)
    if col_edit3.button("Abrir Editor Pop-up"):
        editar_turno_popup(df, sel_g, sel_f)

# --- MÓDULOS ---
def modulo_programacion():
    st.header("📅 Programación y Auditoría")
    repo = conectar_github()
    
    with st.sidebar:
        f_ini = st.date_input("Inicio", datetime(2026, 7, 1))
        f_fin = st.date_input("Fin", datetime(2026, 7, 31))
        if st.button("🚀 Generar Nueva Malla"):
            df_res = generar_malla_base(f_ini, f_fin, repo)
            guardar_excel(df_res, "malla_historica.xlsx")
            st.rerun()

    df_m = cargar_excel("malla_historica.xlsx")
    if not df_m.empty:
        df_view = df_m[(df_m['Fecha_Raw'] >= pd.to_datetime(f_ini)) & (df_m['Fecha_Raw'] <= pd.to_datetime(f_fin))]
        
        # Alertas
        alertas = []
        for g in df_view["Grupo"].unique():
            data = df_view[df_view["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
            for i in range(1, len(data)):
                if not es_cambio_saludable(data[i-1]['Turno'], data[i]['Turno']):
                    alertas.append(f"⚠️ {g}: Salto prohibido el {data[i]['Fecha_Col']}")
        
        if alertas:
            for a in alertas: st.error(a)
        else: st.success("✅ Rotación saludable.")

        renderizar_malla_pro(df_view)

def modulo_detallado():
    st.header("📋 Malla Detallada por Persona")
    df_m, df_e = cargar_excel("malla_historica.xlsx"), cargar_excel("empleados.xlsx")
    if not df_m.empty and not df_e.empty:
        df_det = df_e.merge(df_m, on="Grupo").sort_values("Fecha_Raw")
        orden_cols = df_det["Fecha_Col"].unique()
        matriz_pers = df_det.pivot_table(index=["Nombre", "Grupo"], columns="Fecha_Col", values="Turno", aggfunc='first')[orden_cols]
        st.dataframe(aplicar_estilos(matriz_pers), use_container_width=True)

# --- NAVEGACIÓN ---
with st.sidebar:
    st.image("https://raw.githubusercontent.com/RichGuep/movilgo/main/MovilGo.png", width=150)
    menu = st.radio("MENÚ", ["📅 Programación", "📋 Detallado por Día", "👥 Personal"])

if menu == "📅 Programación": modulo_programacion()
elif menu == "📋 Detallado por Día": modulo_detallado()
elif menu == "👥 Personal":
    df_p = cargar_excel("empleados.xlsx")
    st.data_editor(df_p, use_container_width=True, num_rows="dynamic")
