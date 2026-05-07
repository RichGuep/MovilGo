import streamlit as st
import pandas as pd
import io
from datetime import datetime, timedelta
from github import Github

# --- IMPORTACIÓN DE LÓGICA MOTOR ---
# Asegúrate de que logic_programador.py tenga estas funciones definidas
from logic_programador import (
    generar_malla_base, 
    color_t, 
    es_cambio_saludable, 
    obtener_horario, 
    aplicar_estilos
)

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="MovilGo - Gestión Operativa", 
    layout="wide", 
    initial_sidebar_state="expanded",
    page_icon="⚡"
)

PRIMARY_COLOR = "#1E3D59"
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_GREEN = f"{URL_BASE}logo_empresa_1.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png"
LOGO_BOGOTA = f"{URL_BASE}logo_empresa_3.png"

# --- 2. ESTILOS CSS PERSONALIZADOS ---
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .stButton>button {{ width: 100%; border-radius: 12px; font-weight: bold; transition: 0.3s; }}
    .welcome-card {{ background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%); color: white; padding: 2.5rem; border-radius: 20px; margin-bottom: 2rem; }}
    .metric-card {{ background: white; padding: 15px; border-radius: 10px; border-left: 5px solid {PRIMARY_COLOR}; box-shadow: 0 2px 4px rgba(0,0,0,0.05); margin-bottom: 10px; }}
    .card-empresa {{ background: white; padding: 1.5rem; border-radius: 15px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 2px solid #eee; margin-bottom: 10px; min-height: 200px; }}
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES DE PERSISTENCIA GITHUB ---

def conectar_github():
    try:
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except:
        st.error("❌ Error de conexión con GitHub. Revisa el Token.")
        return None

def cargar_excel(nombre_archivo):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        contents = repo.get_contents(nombre_archivo)
        df = pd.read_excel(io.BytesIO(contents.decoded_content))
        if 'Fecha_Raw' in df.columns: 
            df['Fecha_Raw'] = pd.to_datetime(df['Fecha_Raw'])
        return df
    except:
        return pd.DataFrame()

def guardar_excel(df_nuevo, nombre_archivo):
    repo = conectar_github()
    if not repo: return
    try:
        output = io.BytesIO()
        # Asegurar formato de fecha antes de guardar
        if 'Fecha_Raw' in df_nuevo.columns:
            df_nuevo['Fecha_Raw'] = pd.to_datetime(df_nuevo['Fecha_Raw']).dt.strftime('%Y-%m-%d')
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_nuevo.to_excel(writer, index=False)
            
        try:
            contents = repo.get_contents(nombre_archivo)
            repo.update_file(nombre_archivo, "Sync Malla Data", output.getvalue(), contents.sha)
        except:
            repo.create_file(nombre_archivo, "Initial Data", output.getvalue())
        st.success(f"✅ {nombre_archivo} actualizado.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 4. MÓDULOS DE LA APLICACIÓN ---

def modulo_programacion():
    st.header("📅 Programación Maestra")
    repo = conectar_github()
    
    with st.expander("🚀 Generar Nuevo Periodo", expanded=True):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Fecha Inicio", datetime(2026, 7, 1))
        f_fin = c2.date_input("Fecha Fin", datetime(2026, 7, 31))
        
        if st.button("Calcular Malla Automática"):
            # Generamos la malla usando el motor de logic_programador
            df_resultado = generar_malla_base(f_ini, f_fin, repo)
            guardar_excel(df_resultado, "malla_historica.xlsx")
            st.rerun()

    st.divider()
    df_m = cargar_excel("malla_historica.xlsx")
    
    if not df_m.empty:
        # Filtrar vista actual
        df_view = df_m[(df_m['Fecha_Raw'] >= pd.to_datetime(f_ini)) & (df_m['Fecha_Raw'] <= pd.to_datetime(f_fin))]
        
        st.subheader("📊 Resumen de Deuda de Compensatorios")
        grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
        m_cols = st.columns(4)
        for i, g in enumerate(grupos):
            g_data = df_view[df_view["Grupo"] == g]
            deuda = g_data.iloc[-1]["Deuda_Compensatorio"] if not g_data.empty else 0
            color_deuda = "red" if deuda > 0 else "green"
            m_cols[i].markdown(f'<div class="metric-card"><b>{g}</b><br><span style="color:{color_deuda}">Deuda: {deuda} días</span></div>', unsafe_allow_html=True)

        st.subheader("✍️ Editor de Turnos (Vista por Grupos)")
        # Pivotar para edición
        matriz = df_view.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        # Mostrar con colores
        st.dataframe(aplicar_estilos(matriz), use_container_width=True)
        
        with st.expander("📝 Editar valores manualmente"):
            matriz_editada = st.data_editor(matriz, use_container_width=True)
            if st.button("💾 Guardar Cambios Manuales"):
                # Lógica para reconstruir el dataframe largo y guardar
                df_edit = matriz_editada.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
                df_upd = df_view.drop(columns=['Turno']).merge(df_edit, on=['Grupo', 'Fecha_Col'])
                guardar_excel(df_upd, "malla_historica.xlsx")
                st.rerun()

def modulo_detallado():
    st.header("📋 Detallado por Persona")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx") # Usamos empleados.xlsx según tu archivo
    
    if not df_m.empty and not df_e.empty:
        # Unir personal con la malla por Grupo
        df_det = df_e.merge(df_m, on="Grupo")
        
        # Crear vista de matriz
        matriz_pers = df_det.pivot_table(
            index=["Nombre", "Grupo"], 
            columns="Fecha_Col", 
            values="Turno", 
            aggfunc='first'
        )
        
        st.info("Visualización de turnos asignados por nombre de colaborador.")
        st.dataframe(aplicar_estilos(matriz_pers), use_container_width=True)
    else:
        st.warning("⚠️ Se requiere 'malla_historica.xlsx' y 'empleados.xlsx' en GitHub.")

def modulo_nomina():
    st.header("💰 Reporte de Nómina")
    df_m = cargar_excel("malla_historica.xlsx")
    df_e = cargar_excel("empleados.xlsx")
    
    if not df_m.empty and not df_e.empty:
        df_nom = df_e.merge(df_m, on="Grupo")
        # Aplicar mapeo de horarios desde la lógica
        df_nom["Hora Inicio"], df_nom["Hora Fin"] = zip(*df_nom["Turno"].map(obtener_horario))
        
        st.subheader("Cálculo de Jornadas")
        st.dataframe(df_nom[["Fecha_Raw", "Nombre", "Cedula", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]], use_container_width=True)
        
        csv = df_nom.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Reporte CSV", csv, "reporte_nomina.csv", "text/csv")

def modulo_personal():
    st.header("👥 Gestión de Empleados")
    df_emp = cargar_excel("empleados.xlsx")
    st.info("Añade, elimina o edita el personal y asígnalos a un grupo (Grupo 1-4).")
    
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Actualizar Base de Datos"):
        guardar_excel(df_edit, "empleados.xlsx")
        st.rerun()

# --- 5. FLUJO DE NAVEGACIÓN Y LOGIN ---

if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None

if not st.session_state.logged_in:
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(LOGO_APP, use_container_width=True)
        st.subheader("Acceso al Sistema")
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Iniciar Sesión"):
            if u != "" and p != "": # Aquí puedes poner lógica de clave real
                st.session_state.logged_in = True
                st.rerun()

elif st.session_state.empresa is None:
    st.markdown("<h2 style='text-align: center;'>Seleccione Operación</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_GREEN}" width="120"><br><h4>Greenmóvil</h4></div>', unsafe_allow_html=True)
        if st.button("Acceder Greenmóvil"): 
            st.session_state.empresa = "Greenmóvil"
            st.session_state.logo_actual = LOGO_GREEN
            st.rerun()
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_CABLE}" width="120"><br><h4>Cable Móvil</h4></div>', unsafe_allow_html=True)
        if st.button("Acceder Cable Móvil"): 
            st.session_state.empresa = "Cable Móvil"
            st.session_state.logo_actual = LOGO_CABLE
            st.rerun()
    with c3:
        st.markdown(f'<div class="card-empresa"><img src="{LOGO_BOGOTA}" width="120"><br><h4>BogotáMóvil</h4></div>', unsafe_allow_html=True)
        if st.button("Acceder BogotáMóvil"): 
            st.session_state.empresa = "BogotáMóvil"
            st.session_state.logo_actual = LOGO_BOGOTA
            st.rerun()
else:
    # PANEL PRINCIPAL
    with st.sidebar:
        st.image(st.session_state.logo_actual, width=150)
        st.markdown(f"**Operación:** {st.session_state.empresa}")
        st.divider()
        menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "📋 Detallado", "💰 Nómina", "👥 Personal"])
        if st.button("🚪 Cambiar Operación"):
            st.session_state.empresa = None
            st.rerun()

    if menu == "🏠 Inicio":
        st.markdown(f'<div class="welcome-card"><h1>Bienvenido a {st.session_state.empresa}</h1><p>Sistema centralizado de control de turnos y nómina.</p></div>', unsafe_allow_html=True)
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
