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

# --- 2. LÓGICA DE SALUD ---
def siguiente_turno(actual):
    """Secuencia ascendente: T1 -> T2 -> T3 -> T1"""
    ciclo = {"T1": "T2", "T2": "T3", "T3": "T1"}
    return ciclo.get(actual, "T1")

def obtener_horarios(turno):
    h = {"T1": ("05:30", "13:30"), "T2": ("13:30", "21:30"), "T3": ("21:30", "05:30")}
    return h.get(turno, ("OFF", "OFF"))

# --- 3. PANTALLA GESTIÓN ---
def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos")
    if 'df_cable' not in st.session_state:
        try:
            df = pd.read_excel("empleados.xlsx")
            st.session_state.df_cable = df[df['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except: st.error("Falta empleados.xlsx"); return
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 4. PROGRAMADOR DE BLOQUES ESTABLES ---
def pantalla_programador():
    st.title("📅 Programador Richard - Bloques Estables & Salud")
    
    # PARAMETRIZADOR
    with st.sidebar.expander("⚙️ Configuración de Ley", expanded=True):
        config_desc = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            def_val = "Sábado" if g in ["Grupo 1", "Grupo 2"] else "Domingo"
            config_desc[g] = st.selectbox(f"Día Ley {g}", ["Sábado", "Domingo"], index=0 if def_val=="Sábado" else 1)

    if 'df_cable' not in st.session_state: st.warning("⚠️ Cargue empleados."); return

    repo = conectar_github()
    estado_base = obtener_ultimo_estado_github(repo)

    c1, c2 = st.columns(2)
    f_ini = c1.date_input("Inicio", datetime.now())
    f_fin = c2.date_input("Fin (Proyección)", datetime.now() + timedelta(days=31))

    if st.button("🚀 Generar Malla en Bloques"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        # Estado actual
        m_t = {g: estado_base[g]["u"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_d = {g: estado_base[g]["d"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_lib = {g: estado_base[g]["lib_mes"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        
        # Para forzar bloques, solo cambiamos turno después de un DESC o COMP
        for fecha in lista_fechas:
            d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
            if fecha.day == 1: m_lib = {g: 0 for g in m_lib}

            # 1. DETERMINAR QUIÉN DESCANSA HOY
            lib = None
            # Descanso de Ley (Sáb/Dom)
            for g, dia_ley in config_desc.items():
                es_dia_ley = (d_idx == 5 and dia_ley == "Sábado") or (d_idx == 6 and dia_ley == "Domingo")
                if es_dia_ley:
                    es_turno_ciclo = False
                    if dia_ley == "Sábado":
                        es_turno_ciclo = (g == "Grupo 1" and s_iso % 2 == 0) or (g == "Grupo 2" and s_iso % 2 != 0)
                    else:
                        es_turno_ciclo = (g == "Grupo 3" and s_iso % 2 == 0) or (g == "Grupo 4" and s_iso % 2 != 0)
                    
                    if es_turno_ciclo:
                        lib = g; m_lib[g] += 1
                    else:
                        m_d[g] += 1 # Deuda por trabajar su día de ley
            
            # Pago de Compensatorio (Lunes a Viernes)
            if d_idx < 5 and lib is None:
                for g in sorted(m_d, key=m_d.get, reverse=True):
                    if m_d[g] > 0 and m_t[g] != "T3": # No se compensa saliendo de noche
                        lib = g; m_d[g] -= 1; break

            # 2. ASIGNACIÓN DE TURNOS (MOTOR DE ESTABILIDAD)
            activos = [g for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] if g != lib]
            hoy_t = {}
            
            for g in activos:
                # REGLA DE BLOQUE: El grupo mantiene el turno de ayer
                turno_ayer = m_t[g]
                if turno_ayer in ["DESC", "COMP"]:
                    # Si ayer descansó, HOY rotamos al siguiente turno de la secuencia
                    # Buscamos el turno que NO esté tomado por otro activo
                    sug = siguiente_turno(turno_ayer if turno_ayer not in ["DESC", "COMP"] else "T1") 
                    # Nota: La lógica real de rotación tras descanso se ajusta abajo para evitar colisiones
                    hoy_t[g] = turno_ayer 
                else:
                    hoy_t[g] = turno_ayer

            # Ajuste de Cobertura para asegurar T1, T2, T3 entre los 3 activos
            # Si hay repetidos o falta un turno, reasignamos al que viene de descanso
            asignados = {}
            # Primero fijamos a los que NO pueden cambiar (los que trabajaron ayer)
            for g in activos:
                if m_t[g] not in ["DESC", "COMP"]:
                    asignados[g] = m_t[g]
            
            # Luego asignamos al que viene de descanso el turno que falte
            turnos_faltantes = [t for t in ["T1", "T2", "T3"] if t not in asignados.values()]
            for g in activos:
                if g not in asignados:
                    if turnos_faltantes:
                        nuevo_t = turnos_faltantes.pop(0)
                        # Validamos que no sea un salto hacia atrás
                        if m_t[g] == "T3" and nuevo_t in ["T1", "T2"]:
                            # Si es T3 a T1, es válido porque hubo un día de descanso (lib) en medio
                            pass 
                        asignados[g] = nuevo_t
                    else:
                        asignados[g] = "T2" # Refuerzo por defecto

            # 3. REGISTRO
            for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
                t_f = ("DESC" if d_idx >= 5 else "COMP") if g == lib else asignados.get(g, "T1")
                h_i, h_f = obtener_horarios(t_f)
                
                pers = st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g]
                for _, p in pers.iterrows():
                    resultados.append({
                        "Fecha": fecha.strftime('%Y-%m-%d'), "Nombre": p['Nombre'], "Cargo": p['Cargo'], 
                        "Cedula": p['Cedula'], "Hora Inicio": h_i, "Hora Fin": h_f, "Grupo": g, 
                        "Turno": t_f, "Fecha_Col": f_col, "Mes": fecha.strftime('%B %Y'),
                        "Descansos_Ley_Mes": m_lib[g], "Deuda": m_d[g], "Fecha_Raw": pd.to_datetime(fecha)
                    })
                m_t[g] = t_f

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    # RENDER
    if st.session_state.get('malla_generada') is not None:
        df = st.session_state.malla_generada
        df_m = df.drop_duplicates(['Grupo', 'Fecha_Raw'])
        st.subheader("📊 Matriz Estables (Bloques de 4-6 días)")
        mat = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        def estilo(v):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(v, "#31333F")}; color: white; font-weight: bold; border: 1px solid white'
        st.dataframe(mat.style.map(estilo), use_container_width=True)
        
        st.subheader("📋 Malla Detallada")
        st.dataframe(df[["Fecha", "Nombre", "Cargo", "Cedula", "Hora Inicio", "Hora Fin", "Grupo", "Turno"]], hide_index=True)
