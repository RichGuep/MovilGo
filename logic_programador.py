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
                    "d_trab": int(u.get('Dias_Trabajados_Seguidos', 0))
                }
            else:
                estado[g] = {"u": "T1", "n": 0, "d": 0, "d_trab": 0}
        return estado
    except:
        return {g: {"u": "T1", "n": 0, "d": 0, "d_trab": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

# --- 2. MOTOR DE ROTACIÓN ---
def rotar_turno(actual):
    secuencia = {"T1": "T2", "T2": "T3", "T3": "T1"}
    return secuencia.get(actual, "T1")

def obtener_horarios(turno):
    h = {"T1": ("05:30", "13:30"), "T2": ("13:30", "21:30"), "T3": ("21:30", "05:30")}
    return h.get(turno, ("OFF", "OFF"))

# --- 3. PROGRAMADOR ---
def pantalla_programador():
    st.title("📅 Programador Richard - Control de Descansos 2025")
    
    with st.sidebar.expander("⚙️ Configuración Día de Ley", expanded=True):
        config_desc = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            def_idx = 0 if g in ["Grupo 1", "Grupo 2"] else 1
            config_desc[g] = st.selectbox(f"Día Ley {g}", ["Sábado", "Domingo"], index=def_idx)

    if 'df_cable' not in st.session_state: st.warning("⚠️ Cargue empleados."); return

    repo = conectar_github()
    estado_base = obtener_ultimo_estado_github(repo)

    f_ini = st.date_input("Inicio", datetime.now())
    f_fin = st.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla con Descansos Reales"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        # Variables de control
        m_t = {g: estado_base[g]["u"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_d = {g: estado_base[g]["d"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_trab = {g: estado_base[g]["d_trab"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

        for fecha in lista_fechas:
            d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
            
            # --- 1. DETERMINAR QUIÉN DEBE DESCANSAR ---
            hoy_libera = None
            
            # Prioridad A: Descanso de Ley (Sáb/Dom)
            for g, dia_pactado in config_desc.items():
                es_dia = (d_idx == 5 and dia_pactado == "Sábado") or (d_idx == 6 and dia_pactado == "Domingo")
                if es_dia:
                    # Alternancia: una semana descansa un grupo, la otra el otro
                    if (g in ["Grupo 1", "Grupo 3"] and s_iso % 2 == 0) or (g in ["Grupo 2", "Grupo 4"] and s_iso % 2 != 0):
                        hoy_libera = g
                    else:
                        m_d[g] += 1 # Genera deuda para pagar entre semana
            
            # Prioridad B: Pagar deudas (Lunes a Viernes) o forzar descanso si lleva 6 días
            if d_idx < 5 and hoy_libera is None:
                # Ordenar por el que más días lleva trabajando o más deudas tiene
                prioridad = sorted(m_trab, key=lambda x: (m_trab[x] > 5, m_d[x]), reverse=True)
                for g in prioridad:
                    if (m_d[g] > 0 or m_trab[g] > 5) and m_t[g] != "T3":
                        hoy_libera = g
                        if m_d[g] > 0: m_d[g] -= 1
                        break

            # --- 2. ASIGNAR TURNOS ---
            activos = [g for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] if g != hoy_libera]
            nuevos_turnos = {}
            
            for g in activos:
                # Si ayer descansó, HOY rotamos turno
                if m_t[g] in ["DESC", "COMP"]:
                    nuevos_turnos[g] = rotar_turno(m_t[g] if m_t[g] not in ["DESC", "COMP"] else "T1")
                else:
                    # Mantiene el bloque estable
                    nuevos_turnos[g] = m_t[g]

            # --- 3. BALANCE DE COBERTURA ---
            # Asegurar que los 3 activos cubran T1, T2 y T3 sin repetirse
            existentes = list(nuevos_turnos.values())
            for g in activos:
                # Si el turno está duplicado, el que viene de descanso se ajusta
                if existentes.count(nuevos_turnos[g]) > 1 and m_t[g] in ["DESC", "COMP"]:
                    faltante = [t for t in ["T1", "T2", "T3"] if t not in nuevos_turnos.values()][0]
                    nuevos_turnos[g] = faltante
                    existentes = list(nuevos_turnos.values())

            # --- 4. REGISTRO ---
            for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
                es_lib = (g == hoy_libera)
                t_hoy = ("DESC" if d_idx >= 5 else "COMP") if es_lib else nuevos_turnos.get(g, "T1")
                h_i, h_f = obtener_horarios(t_hoy)
                
                # Actualizar contador de días seguidos
                m_trab[g] = 0 if es_lib else m_trab[g] + 1
                
                for _, p in st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g].iterrows():
                    resultados.append({
                        "Fecha": fecha.strftime('%Y-%m-%d'), "Nombre": p['Nombre'], "Grupo": g, 
                        "Turno": t_hoy, "Hora Inicio": h_i, "Hora Fin": h_f, "Fecha_Col": f_col,
                        "Días Seguidos": m_trab[g], "Deuda": m_d[g], "Fecha_Raw": pd.to_datetime(fecha)
                    })
                m_t[g] = t_hoy

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    if st.session_state.get('malla_generada') is not None:
        df = st.session_state.malla_generada
        df_m = df.drop_duplicates(['Grupo', 'Fecha_Raw'])
        
        st.subheader("📊 Matriz de Turnos y Descansos")
        mat = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        def estilo(v):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(v, "#31333F")}; color: white; font-weight: bold; border: 1px solid white'
        st.dataframe(mat.style.map(estilo), use_container_width=True)
        
        st.subheader("📋 Auditoría de Trabajo Continuo")
        st.write("Días seguidos trabajados por grupo (No debe superar 6):")
        mat_trab = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Días Seguidos")
        st.dataframe(mat_trab, use_container_width=True)
