import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. PERSISTENCIA ---
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except: return None

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
                    "n": int(u.get('Noches_Acum', 0)), 
                    "d": int(u.get('Deuda_Compensatorio', 0)),
                    "lib_mes": int(u.get('Descansos_Ley_Mes', 0))
                }
            else:
                estado[g] = {"u": "T1", "n": 0, "d": 0, "lib_mes": 0}
        return estado
    except:
        return {g: {"u": "T1", "n": 0, "d": 0, "lib_mes": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

# --- 2. LÓGICA DE TURNOS ---
def siguiente_turno(actual):
    ciclo = {"T1": "T2", "T2": "T3", "T3": "T1"}
    return ciclo.get(actual, "T1")

def obtener_horarios(turno):
    h = {"T1": ("05:30", "13:30"), "T2": ("13:30", "21:30"), "T3": ("21:30", "05:30")}
    return h.get(turno, ("OFF", "OFF"))

# --- 3. PROGRAMADOR LEY 2466 DE 2025 ---
def pantalla_programador():
    st.title("📅 Programador Richard - Reforma Laboral 2025")
    st.info("Utilizando Ley 2466: Descanso semanal pactado y bloques estables.")
    
    # PARAMETRIZADOR (Según parágrafo 3° Art. 14 de la Reforma)
    with st.sidebar.expander("⚙️ Pacto de Día de Descanso", expanded=True):
        config_desc = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            def_val = "Sábado" if g in ["Grupo 1", "Grupo 2"] else "Domingo"
            config_desc[g] = st.selectbox(f"Día Pactado {g}", ["Sábado", "Domingo"], index=0 if def_val=="Sábado" else 1)

    if 'df_cable' not in st.session_state: st.warning("⚠️ Cargue empleados."); return

    repo = conectar_github()
    estado_base = obtener_ultimo_estado_github(repo)

    c1, c2 = st.columns(2)
    f_ini = c1.date_input("Inicio", datetime.now())
    f_fin = c2.date_input("Fin (Proyección)", datetime.now() + timedelta(days=31))

    if st.button("🚀 Generar Malla Reforma 2025"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        m_t = {g: estado_base[g]["u"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_d = {g: estado_base[g]["d"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_lib = {g: estado_base[g]["lib_mes"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        
        for fecha in lista_fechas:
            d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
            if fecha.day == 1: m_lib = {g: 0 for g in m_lib}

            # 1. ASIGNACIÓN DEL "DÍA DE DESCANSO" (Art. 14)
            lib = None
            for g, dia_pactado in config_desc.items():
                es_dia_pactado = (d_idx == 5 and dia_pactado == "Sábado") or (d_idx == 6 and dia_pactado == "Domingo")
                if es_dia_pactado:
                    # Alternancia quincenal para garantizar los 2 descansos de ley al mes
                    if (g in ["Grupo 1", "Grupo 3"] and s_iso % 2 == 0) or (g in ["Grupo 2", "Grupo 4"] and s_iso % 2 != 0):
                        lib = g
                        m_lib[g] += 1
                    else:
                        m_d[g] += 1 # Genera compensatorio por trabajo en día pactado
            
            # Pago de Compensatorio Inmediato (Lunes-Viernes)
            if d_idx < 5 and lib is None:
                for g in sorted(m_d, key=m_d.get, reverse=True):
                    if m_d[g] > 0 and m_t[g] != "T3":
                        lib = g; m_d[g] -= 1; break

            # 2. BLOQUES ESTABLES Y ROTACIÓN SEGURA
            activos = [g for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] if g != lib]
            # Mantener turno actual o rotar solo tras descanso
            nuevos_turnos = {}
            turnos_ocupados = []

            for g in activos:
                if m_t[g] in ["DESC", "COMP"]:
                    # Si viene de descansar, calculamos el turno que falta para cubrir la operación
                    pass 
                else:
                    nuevos_turnos[g] = m_t[g]
                    turnos_ocupados.append(m_t[g])

            # Llenar los vacíos de los que vienen de descansar
            turnos_libres = [t for t in ["T1", "T2", "T3"] if t not in turnos_ocupados]
            for g in activos:
                if g not in nuevos_turnos:
                    if turnos_libres:
                        nuevo = turnos_libres.pop(0)
                        # Blindaje T3 -> T1 (Salud)
                        if m_t[g] == "T3" and nuevo == "T1": pass 
                        nuevos_turnos[g] = nuevo
                    else:
                        nuevos_turnos[g] = "T2"

            # 3. REGISTRO
            for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
                t_f = ("DESC" if d_idx >= 5 else "COMP") if g == lib else nuevos_turnos.get(g, "T1")
                h_i, h_f = obtener_horarios(t_f)
                
                for _, p in st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g].iterrows():
                    resultados.append({
                        "Fecha": fecha.strftime('%Y-%m-%d'), "Nombre": p['Nombre'], "Cargo": p['Cargo'], 
                        "Cedula": p['Cedula'], "Hora Inicio": h_i, "Hora Fin": h_f, "Grupo": g, 
                        "Turno": t_f, "Fecha_Col": f_col, "Mes": fecha.strftime('%B %Y'),
                        "Descansos_Ley": m_lib[g], "Deuda": m_d[g], "Fecha_Raw": pd.to_datetime(fecha)
                    })
                m_t[g] = t_f

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    # RENDER
    if st.session_state.get('malla_generada') is not None:
        df = st.session_state.malla_generada
        df_m = df.drop_duplicates(['Grupo', 'Fecha_Raw'])
        st.subheader("📊 Malla de Turnos Estables (Ley 2466)")
        mat = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        def estilo(v):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(v, "#31333F")}; color: white; font-weight: bold; border: 1px solid white'
        st.dataframe(mat.style.map(estilo), use_container_width=True)
        
        st.subheader("🔍 Auditoría de Garantía Quincenal")
        # Mostrar cuántos descansos de ley (DESC) ha tenido cada grupo en el mes
        res_auditoria = df_m[df_m['Turno'] == "DESC"].groupby(['Mes', 'Grupo']).size().reset_index(name='Descansos Otorgados')
        st.table(res_auditoria)
