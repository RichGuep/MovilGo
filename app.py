import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="MovilGo - Gestión Integral", layout="wide", initial_sidebar_state="collapsed")

# --- URLs DE IMÁGENES GITHUB ---
# Asegúrate de que las rutas sean correctas en tu repo 'RichGuep/movilgo'
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png" 
LOGO_BOGOTA = f"{URL_BASE}logo_empresa_3.png" 
LOGO_GREEN = f"{URL_BASE}logo_empresa_1.png" 

# --- ESTILOS CSS PERSONALIZADOS ---
st.markdown(f"""
    <style>
    .main {{ background-color: #f8f9fa; }}
    [data-testid="stMetricValue"] {{ font-size: 1.8rem; color: #1f77b4; }}
    .stButton>button {{ width: 100%; border-radius: 10px; font-weight: bold; transition: 0.3s; }}
    .card {{
        background-color: white;
        padding: 25px;
        border-radius: 20px;
        box-shadow: 0 10px 15px rgba(0,0,0,0.05);
        text-align: center;
        border: 1px solid #eee;
        margin-bottom: 10px;
    }}
    .card img {{ width: 120px; height: 120px; object-fit: contain; margin-bottom: 15px; }}
    .stDataEditor {{ border-radius: 15px; overflow: hidden; }}
    </style>
    """, unsafe_allow_html=True)

# --- 1. FUNCIONES DE CORE (GITHUB Y SALUD) ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ GITHUB_TOKEN no encontrado en Secrets.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df_hist = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_hist['Fecha_Raw'] = pd.to_datetime(df_hist['Fecha_Raw'])
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw')
            if not regs.empty:
                u = regs.iloc[-1]
                estado[g] = {
                    "u": u['Turno'], 
                    "n": int(u.get('Noches_Acum', 0)) if u['Turno'] == "T3" else 0,
                    "d": int(u.get('Deuda_Compensatorio', 0))
                }
            else:
                estado[g] = {"u": "DESC", "n": 0, "d": 0}
        return estado
    except:
        return {g: {"u": "DESC", "n": 0, "d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

def guardar_malla_en_historico(df_nueva):
    repo = conectar_github()
    if not repo: return
    try:
        try:
            contents = repo.get_contents("malla_historica.xlsx")
            df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
            df_final = pd.concat([df_previo, df_nueva]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
        except:
            df_final = df_nueva
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        contents = repo.get_contents("malla_historica.xlsx")
        repo.update_file("malla_historica.xlsx", "Update Malla MovilGo", output.getvalue(), contents.sha)
        st.success("✅ Sincronizado con GitHub.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"] or hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
    return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold;'

# --- 2. VISTAS DE NAVEGACIÓN ---

def vista_login():
    _, col_cent, _ = st.columns([1, 1.5, 1])
    with col_cent:
        st.image(LOGO_APP, use_container_width=True)
        st.markdown("<h2 style='text-align: center; color: #1e3d59;'>Bienvenido a MovilGo</h2>", unsafe_allow_html=True)
        with st.container(border=True):
            user = st.text_input("Usuario")
            pw = st.text_input("Contraseña", type="password")
            if st.button("Iniciar Sesión"):
                st.session_state.logged_in = True
                st.rerun()

def vista_seleccion_empresa():
    st.markdown("<h2 style='text-align: center;'>Panel de Operaciones</h2>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Seleccione la empresa para gestionar turnos</p>", unsafe_allow_html=True)
    st.write("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f'<div class="card"><img src="{LOGO_GREEN}"><h4>Greenmovil</h4><p style="font-size:0.8em; color:orange;">Próximamente</p></div>', unsafe_allow_html=True)
        st.button("Entrar", key="g1", disabled=True)

    with col2:
        st.markdown(f'<div class="card"><img src="{LOGO_CABLE}"><h4>Cable Móvil</h4><p style="font-size:0.8em; color:green;">Módulo Activo</p></div>', unsafe_allow_html=True)
        if st.button("Entrar", key="c2"):
            st.session_state.empresa = "Cable Móvil"
            st.rerun()

    with col3:
        st.markdown(f'<div class="card"><img src="{LOGO_BOGOTA}"><h4>Bogotá Móvil</h4><p style="font-size:0.8em; color:orange;">Próximamente</p></div>', unsafe_allow_html=True)
        st.button("Entrar", key="b3", disabled=True)

# --- 3. MÓDULO PROGRAMADOR (LÓGICA ANTERIOR REFINADA) ---

def pantalla_programador():
    st.markdown(f"### 🏢 Operación: {st.session_state.empresa}")
    if st.button("⬅️ Volver al Panel Principal"):
        st.session_state.empresa = None
        st.rerun()
    
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    repo = conectar_github()
    if not repo: return

    # --- PANEL LATERAL O SUPERIOR DE CONTROL ---
    with st.expander("⚙️ Configuración de Nueva Malla", expanded=st.session_state.malla_generada is None):
        c1, c2 = st.columns(2)
        f_ini = c1.date_input("Fecha Inicio", datetime.now())
        f_fin = c2.date_input("Fecha Fin", datetime.now() + timedelta(days=28))
        
        if st.button("🚀 Generar Malla Inteligente"):
            estado_ayer = obtener_ultimo_estado_github(repo)
            lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
            resultados = []
            
            mem_t = {g: estado_ayer[g]["u"] for g in grupos_n}
            mem_n = {g: estado_ayer[g]["n"] for g in grupos_n}
            deudas = {g: estado_ayer[g]["d"] for g in grupos_n}
            co_h = holidays.Colombia(years=[2024, 2025, 2026])

            for fecha in lista_fechas:
                fecha_dt = pd.to_datetime(fecha)
                dia_idx = fecha_dt.weekday()
                sem_iso = fecha_dt.isocalendar()[1]
                es_fest = fecha_dt in co_h
                col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

                # Lógica de descansos
                libranza = None
                if dia_idx == 5: # Sab
                    libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                    deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
                elif dia_idx == 6: # Dom
                    libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                    deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
                else:
                    for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                        if deudas[g] > 0 and mem_t[g] != "T3":
                            libranza = g; deudas[g] -= 1; break

                # Asignación de turnos activos
                activos = [g for g in grupos_n if g != libranza]
                turnos_hoy = {}
                for g in activos:
                    idx_g = grupos_n.index(g)
                    t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                    if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
                    if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                    turnos_hoy[g] = t_sug

                # Cobertura mínima
                for tr in ["T1", "T2", "T3"]:
                    if tr not in turnos_hoy.values():
                        for gf in sorted(activos, key=lambda x: (mem_t[x] == "T3")):
                            if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                                if es_cambio_saludable(mem_t[gf], tr):
                                    turnos_hoy[gf] = tr; break
                
                for g in grupos_n:
                    t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                    n_a = mem_n[g] + 1 if t_f == "T3" else 0
                    resultados.append({
                        "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                        "Fecha_Raw": fecha_dt, "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g]
                    })
                    mem_t[g] = t_f; mem_n[g] = n_a

            st.session_state.malla_generada = pd.DataFrame(resultados)
            guardar_malla_en_historico(st.session_state.malla_generada)
            st.rerun()

    # --- ÁREA DE TRABAJO ---
    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())

        st.subheader("✍️ Ajuste Manual y Cobertura")
        fechas_sel = st.multiselect("Filtrar fechas para corregir:", options=list(matriz.columns))
        df_edit = matriz[fechas_sel] if fechas_sel else matriz
        
        config = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"], width="small") for c in df_edit.columns}
        matriz_editada = st.data_editor(df_edit, column_config=config, use_container_width=True)

        if st.button("💾 Guardar Cambios"):
            m_final = matriz.copy()
            m_final.update(matriz_editada)
            df_man = m_final.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = df_res.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            st.session_state.malla_generada = df_final
            guardar_malla_en_historico(df_final)
            st.rerun()

        # --- CENTRO DE ALERTAS ---
        st.divider()
        alertas = []
        for g in grupos_n:
            h = df_res[df_res["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
            for i in range(1, len(h)):
                if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                    alertas.append({"msg": f"⚠️ {g}: Salto {h[i-1]['Turno']} -> {h[i]['Turno']}", "f": h[i]['Fecha_Col']})

        if alertas:
            st.error(f"Se encontraron {len(alertas)} inconsistencias de salud.")
            sel = st.selectbox("Analizar falla:", options=alertas, format_func=lambda x: f"{x['msg']} el {x['f']}")
            st.dataframe(df_res[df_res['Fecha_Col'] == sel['f']][['Grupo', 'Turno']].set_index('Grupo').T)
        else:
            st.success("✅ Malla Saludable: No se detectan saltos prohibidos.")

# --- INICIO DE LA APP ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'empresa' not in st.session_state: st.session_state.empresa = None
if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None

if not st.session_state.logged_in:
    vista_login()
elif st.session_state.empresa is None:
    vista_seleccion_empresa()
else:
    pantalla_programador()
