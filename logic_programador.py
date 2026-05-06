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
                estado[g] = {"u": "DESC", "n": 0, "d": 0, "lib_mes": 0}
        return estado
    except:
        return {g: {"u": "DESC", "n": 0, "d": 0, "lib_mes": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

# --- 2. LÓGICA DE SALUD ---
def es_rotacion_valida(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"]: return True
    if hoy in ["DESC", "COMP", "OFF"]: return True
    niveles = {"T1": 1, "T2": 2, "T3": 3}
    return niveles[hoy] >= niveles[ayer]

def obtener_horarios(turno):
    h = {"T1": ("05:30", "13:30"), "T2": ("13:30", "21:30"), "T3": ("21:30", "05:30")}
    return h.get(turno, ("OFF", "OFF"))

# --- 3. PANTALLAS ---
def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos")
    if 'df_cable' not in st.session_state:
        try:
            df = pd.read_excel("empleados.xlsx")
            st.session_state.df_cable = df[df['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except: st.error("Falta empleados.xlsx"); return
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 4. PROGRAMADOR CON PARAMETRIZADOR ---
def pantalla_programador():
    st.title("📅 Programador Maestro Richard")
    
    # --- PARAMETRIZADOR DE DESCANSOS DE LEY ---
    with st.sidebar.expander("⚙️ Configurar Descansos de Ley", expanded=True):
        st.write("Seleccione el día de descanso asignado:")
        config_desc = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            # Valor por defecto: Grupo 1 y 2 Sábados, 3 y 4 Domingos
            def_val = "Sábado" if g in ["Grupo 1", "Grupo 2"] else "Domingo"
            config_desc[g] = st.selectbox(f"Día Ley {g}", ["Sábado", "Domingo"], index=0 if def_val=="Sábado" else 1)

    if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None
    if 'df_cable' not in st.session_state: st.warning("⚠️ Cargue empleados."); return

    repo = conectar_github()
    estado_base = obtener_ultimo_estado_github(repo)

    c1, c2 = st.columns(2)
    f_ini = c1.date_input("Inicio", datetime.now())
    f_fin = c2.date_input("Fin (Hasta 6 meses)", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla con Parametrizador"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        m_t = {g: estado_base[g]["u"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_n = {g: estado_base[g]["n"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_d = {g: estado_base[g]["d"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_lib = {g: estado_base[g]["lib_mes"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

        for fecha in lista_fechas:
            d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
            # Resetear contador de descansos si es inicio de mes
            if fecha.day == 1: m_lib = {g: 0 for g in m_lib}

            # --- LÓGICA DE DESCANSOS PARAMETRIZADA ---
            lib = None
            
            # Revisar cada grupo para ver si hoy es su día de ley
            for g, dia_ley in config_desc.items():
                es_dia_ley = (d_idx == 5 and dia_ley == "Sábado") or (d_idx == 6 and dia_ley == "Domingo")
                
                if es_dia_ley:
                    # REGLA: Ciclo quincenal (Semana par descansa uno, impar otro)
                    es_turno_liberar = False
                    if dia_ley == "Sábado":
                        es_turno_liberar = (g == "Grupo 1" and s_iso % 2 == 0) or (g == "Grupo 2" and s_iso % 2 != 0)
                    else:
                        es_turno_liberar = (g == "Grupo 3" and s_iso % 2 == 0) or (g == "Grupo 4" and s_iso % 2 != 0)
                    
                    if es_turno_liberar:
                        lib = g
                        m_lib[g] += 1
                    else:
                        # Si no le toca librar hoy por ciclo, genera deuda compensatoria
                        m_d[g] += 1

            # PAGO DE COMPENSATORIOS (Lunes a Viernes)
            if d_idx < 5 and lib is None:
                for g in sorted(m_d, key=m_d.get, reverse=True):
                    if m_d[g] > 0 and m_t[g] != "T3":
                        lib = g; m_d[g] -= 1; break

            # --- ASIGNACIÓN DE TURNOS CON SALUD ---
            activos = [g for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] if g != lib]
            hoy_t = {}
            for g in activos:
                idx = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"].index(g)
                sug = ["T1", "T2", "T3"][(idx + s_iso) % 3]
                
                # Candado Circadiano (Inercia si es T3)
                if m_t[g] == "T3": sug = "T3"
                elif not es_rotacion_valida(m_t[g], sug): sug = m_t[g]
                
                if m_n[g] >= 6 and sug == "T3": sug = "T1"
                hoy_t[g] = sug

            # Ajuste de cobertura (T1, T2, T3)
            for tr in ["T1", "T2", "T3"]:
                if tr not in hoy_t.values():
                    for gf in activos:
                        if list(hoy_t.values()).count(hoy_t[gf]) > 1:
                            if es_rotacion_valida(m_t[gf], tr):
                                hoy_t[gf] = tr; break

            # Registro final
            for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
                t_f = ("DESC" if d_idx >= 5 else "COMP") if g == lib else hoy_t.get(g, "T1")
                h_i, h_f = obtener_horarios(t_f)
                n_a = m_n[g] + 1 if t_f == "T3" else 0
                
                # Alerta si no se cumple el mínimo quincenal al final del mes
                alerta = ""
                if fecha.day > 25 and m_lib[g] < 2:
                    alerta = "🚨 RIESGO: Menos de 2 descansos de ley"

                pers = st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g]
                for _, p in pers.iterrows():
                    resultados.append({
                        "Fecha": fecha.strftime('%Y-%m-%d'), "Nombre": p['Nombre'], "Cargo": p['Cargo'], 
                        "Cedula": p['Cedula'], "Hora Inicio": h_i, "Hora Fin": h_f, "Grupo": g, 
                        "Turno": t_f, "Fecha_Col": f_col, "Mes": fecha.strftime('%B %Y'), 
                        "Noches_Acum": n_a, "Descansos_Ley_Mes": m_lib[g], "Alerta": alerta,
                        "Deuda_Compensatorio": m_d[g], "Fecha_Raw": pd.to_datetime(fecha)
                    })
                m_t[g], m_n[g] = t_f, n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    # --- RENDERIZADO VISUAL ---
    if st.session_state.get('malla_generada') is not None:
        df = st.session_state.malla_generada
        df_m = df.drop_duplicates(['Grupo', 'Fecha_Raw'])
        
        st.subheader("📊 Matriz de Turnos")
        mat = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        def estilo_turnos(v):
            colors = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {colors.get(v, "#31333F")}; color: white; font-weight: bold'
        st.dataframe(mat.style.map(estilo_turnos), use_container_width=True)

        st.subheader("🔍 Auditoría Richard: Descansos de Ley (Mínimo 2/mes)")
        # Verificación de descansos de ley reales por mes
        res_ley = df_m[df_m['Turno'] == "DESC"].drop_duplicates(['Grupo', 'Fecha_Raw'])
        if not res_ley.empty:
            st.table(res_ley.groupby(['Mes', 'Grupo']).size().rename("Descansos de Ley Otorgados"))

        st.subheader("📋 Malla Operativa Individual")
        st.dataframe(df[["Fecha", "Nombre", "Cargo", "Cedula", "Hora Inicio", "Hora Fin", "Grupo", "Turno", "Alerta"]], hide_index=True)
