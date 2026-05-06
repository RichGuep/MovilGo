import streamlit as st
import pandas as pd
import logic as lg  # Importa todas las funciones del motor lógico
from datetime import datetime, timedelta

# --- CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(
    page_title="MovilGo - Gestión de Flotas", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- ESTILOS VISUALES Y CONTRASTE ---
PRIMARY_COLOR = "#1E3D59" 
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stSidebar"] {{ background-color: {PRIMARY_COLOR}; }}
    [data-testid="stSidebar"] * {{ color: white !important; }}
    .stButton>button {{ width: 100%; border-radius: 12px; font-weight: bold; height: 3em; transition: 0.3s; }}
    .welcome-card {{
        background: linear-gradient(135deg, {PRIMARY_COLOR} 0%, #3a6073 100%);
        color: white; padding: 2.5rem; border-radius: 20px; box-shadow: 0 10px 25px rgba(0,0,0,0.1);
        margin-bottom: 2rem;
    }}
    .card-empresa {{
        background-color: white; padding: 25px; border-radius: 20px;
        text-align: center; border: 1px solid #eee; transition: 0.4s; height: 280px;
    }}
    </style>
    """, unsafe_allow_html=True)

# --- INICIALIZACIÓN DE ESTADO ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None
if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None

# --- VISTAS DE NAVEGACIÓN ---

def vista_login():
    _, col, _ = st.columns([1, 1.2, 1])
    with col:
        st.image(lg.LOGO_APP, use_container_width=True)
        st.markdown("<h2 style='text-align:center;'>Acceso Operativo</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            user = st.text_input("Usuario")
            pw = st.text_input("Clave", type="password")
            if st.button("Ingresar"):
                st.session_state.logged_in = True
                st.rerun()

def vista_seleccion_empresa():
    st.markdown("<h2 style='text-align:center;'>Seleccione la Operación</h2>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    with c2:
        st.markdown(f'<div class="card-empresa"><img src="{lg.LOGO_CABLE}" width="100"><h3>Cable Móvil</h3><p>Módulo de Gestión 24/7</p></div>', unsafe_allow_html=True)
        if st.button("Acceder a Cable Móvil"):
            st.session_state.empresa = "Cable Móvil"
            st.rerun()
    # Otros módulos deshabilitados (Green y Bogotá)

# --- MÓDULOS DEL MENÚ (CABLE MÓVIL) ---

def modulo_inicio():
    st.markdown(f'<div class="welcome-card"><h1>Bienvenido a {st.session_state.empresa}</h1><p>Sistema de gestión saludable y continuidad operativa.</p></div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)
    df_p = lg.cargar_excel("empleados.xlsx")
    c1.metric("Técnicos Activos", len(df_p))
    c2.metric("Estado Malla", "Sincronizada" if st.session_state.malla_generada is not None else "Pendiente")
    c3.metric("Operación", "Estable")

def modulo_programacion():
    st.header("📅 Programación Maestra (Grupos)")
    repo = lg.conectar_github()
    
    with st.expander("🚀 Generar Nuevo Periodo", expanded=st.session_state.malla_generada is None):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Inicio de periodo", datetime.now())
        f_fin = c2.date_input("Fin de periodo", datetime.now() + timedelta(days=28))
        
        if st.button("Generar Malla con Motor Logic"):
            # Llama a la lógica pura de logic.py
            # [Aquí el sistema ejecuta el motor de rotación y persistencia histórica]
            st.session_state.malla_generada = lg.generar_malla_base(f_ini, f_fin, repo)
            lg.guardar_malla_en_historico(st.session_state.malla_generada)
            st.rerun()

    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_res["Fecha_Col"].unique())
        
        st.subheader("✍️ Editor Maestro")
        fechas_sel = st.multiselect("Filtrar fechas para ajustar:", options=list(matriz.columns))
        df_edit_view = matriz[fechas_sel] if fechas_sel else matriz
        
        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in df_edit_view.columns}
        matriz_editada = st.data_editor(df_edit_view, column_config=config_col, use_container_width=True)

        if st.button("💾 Guardar y Aplicar Cambios"):
            matriz_final = matriz.copy(); matriz_final.update(matriz_editada)
            df_man = matriz_final.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = df_res.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            st.session_state.malla_generada = df_final
            lg.guardar_malla_en_historico(df_final)
            st.rerun()

        # Alertas de Saltos (Usando validación de logic.py)
        st.divider()
        alertas = lg.validar_malla_saludable(df_res)
        if alertas:
            sel = st.selectbox("⚠️ Fallas de Salud Detectadas:", options=alertas, format_func=lambda x: f"{x['msg']} el {x['f']}")
            st.warning(f"Error en {sel['grupo']}. Revisa la cobertura:")
            st.dataframe(df_res[df_res['Fecha_Col'] == sel['f']][['Grupo', 'Turno']].set_index('Grupo').T)
        else:
            st.success("✅ Rotación saludable garantizada.")

def modulo_detallado():
    st.header("📋 Detallado Programación (Persona)")
    df_m = lg.cargar_excel("malla_historica.xlsx")
    df_e = lg.cargar_excel("empleados.xlsx")
    
    if df_m.empty or df_e.empty:
        st.warning("Debe generar la malla y el personal primero.")
        return

    # Dashboard Analítico
    st.subheader("📊 Analítica de Malla")
    d1, d2, d3 = st.columns(3)
    d1.bar_chart(df_m[df_m["Turno"].isin(["DESC", "COMP"])].groupby("Grupo").size())
    d2.dataframe(df_m.groupby(["Grupo", "Turno"]).size().unstack(fill_value=0))
    d3.bar_chart(df_m[df_m["Turno"] == "T3"].groupby("Grupo").size())

    # Malla Detallada Persona vs Fecha
    df_det = df_e.merge(df_m, on="Grupo")
    matriz_full = df_det.pivot_table(index=["Grupo", "Nombre"], columns="Fecha_Col", values="Turno", aggfunc='first').reindex(columns=df_m["Fecha_Col"].unique())
    st.dataframe(matriz_full.style.map(lg.color_t), use_container_width=True)

def modulo_nomina():
    st.header("💰 Módulo de Nómina")
    df_m = lg.cargar_excel("malla_historica.xlsx")
    df_e = lg.cargar_excel("empleados.xlsx")
    
    if df_m.empty or df_e.empty: return

    # Merge y aplicación de horarios desde Logic
    df_nom = df_e.merge(df_m, on="Grupo")
    df_nom["Hora Inicio"], df_nom["Hora Fin"] = zip(*df_nom["Turno"].map(lg.obtener_horario))
    
    reporte = df_nom[["Fecha_Raw", "Nombre", "Cedula", "Cargo", "Grupo", "Turno", "Hora Inicio", "Hora Fin"]].sort_values(["Fecha_Raw", "Nombre"])
    reporte["Fecha_Raw"] = pd.to_datetime(reporte["Fecha_Raw"]).dt.date
    st.dataframe(reporte, use_container_width=True, hide_index=True)
    st.download_button("📥 Exportar CSV", reporte.to_csv(index=False).encode('utf-8'), "nomina_movilgo.csv")

def modulo_personal():
    st.header("👥 Gestión de Personal")
    df_emp = lg.cargar_excel("empleados.xlsx")
    df_edit = st.data_editor(df_emp, use_container_width=True, num_rows="dynamic")
    if st.button("💾 Guardar Personal"):
        lg.guardar_excel_generico(df_edit, "empleados.xlsx", "Update Personal")
        st.rerun()

# --- FLUJO PRINCIPAL ---

if not st.session_state.logged_in:
    vista_login()
elif st.session_state.empresa is None:
    vista_seleccion_empresa()
else:
    with st.sidebar:
        st.image(lg.LOGO_CABLE, width=150)
        st.divider()
        menu = st.radio("MENÚ", ["🏠 Inicio", "📅 Programación", "📋 Detallado Programación", "💰 Nómina", "👥 Personal"])
        if st.button("🚪 Cambiar Empresa"):
            st.session_state.empresa = None
            st.rerun()

    if menu == "🏠 Inicio": modulo_inicio()
    elif menu == "📅 Programación": modulo_programacion()
    elif menu == "📋 Detallado Programación": modulo_detallado()
    elif menu == "💰 Nómina": modulo_nomina()
    elif menu == "👥 Personal": modulo_personal()
