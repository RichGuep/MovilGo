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
                estado[g] = {"u": u['Turno'], "n": int(u.get('Noches_Acum', 0)), "d": int(u.get('Deuda_Compensatorio', 0))}
            else:
                estado[g] = {"u": "DESC", "n": 0, "d": 0}
        return estado
    except:
        return {g: {"u": "DESC", "n": 0, "d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

# --- 2. LÓGICA DE SALUD Y HORARIOS ---
def es_rotacion_valida(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"]: return True
    if hoy in ["DESC", "COMP", "OFF"]: return True
    niveles = {"T1": 1, "T2": 2, "T3": 3}
    return niveles[hoy] >= niveles[ayer]

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

# --- 4. PROGRAMADOR CON BLINDAJE SEMANAL ---
def pantalla_programador():
    st.title("📅 Programador Richard - Blindaje Legal 7 Días")
    
    if 'malla_generada' not in st.session_state: st.session_state.malla_generada = None
    if 'df_cable' not in st.session_state: st.warning("⚠️ Cargue empleados."); return

    repo = conectar_github()
    estado_base = obtener_ultimo_estado_github(repo)

    c1, c2 = st.columns(2)
    f_ini = c1.date_input("Inicio", datetime.now())
    f_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla Blindada"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        m_t = {g: estado_base[g]["u"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_n = {g: estado_base[g]["n"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_d = {g: estado_base[g]["d"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

        for fecha in lista_fechas:
            d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
            
            # --- MOTOR DE DESCANSOS IMPLACABLE ---
            lib = None
            
            # 1. Sábados y Domingos: Descansos por ciclo
            if d_idx == 5: 
                lib = "Grupo 1" if s_iso % 2 == 0 else "Grupo 2"
                # El grupo que DEBÍA descansar y trabajó, genera deuda inmediata
                m_d["Grupo 2" if s_iso % 2 == 0 else "Grupo 1"] += 1 
            elif d_idx == 6: 
                lib = "Grupo 3" if s_iso % 2 == 0 else "Grupo 4"
                m_d["Grupo 4" if s_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # 2. Lunes a Viernes: PAGO OBLIGATORIO DE DEUDA
                # Si alguien debe un día, DESCANSA HOY (si no viene de T3)
                # Ordenamos para que el que más debe, descanse primero en la semana
                for g in sorted(m_d, key=m_d.get, reverse=True):
                    if m_d[g] > 0 and m_t[g] != "T3":
                        lib = g
                        m_d[g] -= 1 # Deuda saldada
                        break

            # --- ASIGNACIÓN DE TURNOS (CANDADO DE SALUD) ---
            activos = [g for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] if g != lib]
            hoy_t = {}
            alertas_dia = {}

            for g in activos:
                idx = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"].index(g)
                sug = ["T1", "T2", "T3"][(idx + s_iso) % 3]
                
                # Respetar rotación ascendente (No T3 -> T1)
                if not es_rotacion_valida(m_t[g], sug): sug = m_t[g]
                if m_n[g] >= 6 and sug == "T3": sug = "T1"
                
                hoy_t[g] = sug
                alertas_dia[g] = "" if es_rotacion_valida(m_t[g], sug) else f"⚠️ {m_t[g]} -> {sug}"

            # T3 único y Refuerzo T2
            while list(hoy_t.values()).count("T3") > 1:
                for gn in activos:
                    if hoy_t[gn] == "T3" and m_t[gn] != "T3": hoy_t[gn] = "T2"; break

            # Registro final
            for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
                t_f = ("DESC" if d_idx >= 5 else "COMP") if g == lib else hoy_t.get(g, "T1")
                h_i, h_f = obtener_horarios(t_f)
                n_a = m_n[g] + 1 if t_f == "T3" else 0
                
                pers = st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g]
                for _, p in pers.iterrows():
                    resultados.append({
                        "Fecha": fecha.strftime('%Y-%m-%d'), "Nombre": p['Nombre'], "Cargo": p['Cargo'], 
                        "Cedula": p['Cedula'], "Hora Inicio": h_i, "Hora Fin": h_f, "Grupo": g, 
                        "Turno": t_f, "Fecha_Col": f_col, "Mes": fecha.strftime('%B %Y'), 
                        "Noches_Acum": n_a, "Alerta": alertas_dia.get(g, ""), 
                        "Deuda_Pendiente": m_d[g], "Fecha_Raw": pd.to_datetime(fecha)
                    })
                m_t[g], m_n[g] = t_f, n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    # --- VISTA FINAL ---
    if st.session_state.get('malla_generada') is not None:
        df = st.session_state.malla_generada
        df_m = df.drop_duplicates(['Grupo', 'Fecha_Raw'])
        
        st.subheader("📊 Matriz de Turnos (Colores)")
        mat = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        def estilo_turnos(v):
            colors = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {colors.get(v, "#31333F")}; color: white; font-weight: bold; border: 1px solid white'
        st.dataframe(mat.style.map(estilo_turnos), use_container_width=True)

        st.subheader("🔍 Auditoría Richard: Descansos y Deudas")
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Conteo de Descansos (Debe haber 4 o 5 por mes):**")
            res = df[df['Turno'].isin(['DESC', 'COMP'])].drop_duplicates(['Grupo', 'Fecha_Raw'])
            if not res.empty: st.table(res.groupby(['Mes', 'Grupo', 'Turno']).size().unstack(fill_value=0))
        with c2:
            st.write("**Deuda al final del periodo (Debe ser 0):**")
            # Esto muestra cuántos días se quedaron debiendo. Si es > 0, hay que revisar.
            deuda_final = df_m.drop_duplicates('Grupo', keep='last')[['Grupo', 'Deuda_Pendiente']]
            st.table(deuda_final)

        st.subheader("📋 Malla Detallada (Nombre / Cédula / Horas)")
        st.dataframe(df[["Fecha", "Nombre", "Cargo", "Cedula", "Hora Inicio", "Hora Fin", "Grupo", "Turno", "Deuda_Pendiente"]], hide_index=True)
