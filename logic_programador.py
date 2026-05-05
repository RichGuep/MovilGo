import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. CONEXIÓN Y PERSISTENCIA GITHUB ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except:
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
        repo.update_file("malla_historica.xlsx", "Malla Richard Color + Auditoria", output.getvalue(), contents.sha)
    except:
        pass

# --- 2. MOTOR DE SALUD Y HORARIOS ---

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
            df.columns = df.columns.str.strip()
            st.session_state.df_cable = df[df['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except:
            st.error("No se encontró empleados.xlsx")
            return
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

def pantalla_programador():
    st.title("📅 Programador Richard (Color & Auditoría)")
    
    # Inicialización segura
    if 'malla_generada' not in st.session_state:
        st.session_state.malla_generada = None

    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Cargue empleados en Gestión de Grupos.")
        return

    repo = conectar_github()
    estado_base = obtener_ultimo_estado_github(repo)

    c1, c2 = st.columns(2)
    f_ini = c1.date_input("Inicio", datetime.now())
    f_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar y Auditar"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        m_t = {g: estado_base[g]["u"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_n = {g: estado_base[g]["n"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}
        m_d = {g: estado_base[g]["d"] for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

        for fecha in lista_fechas:
            d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
            
            # --- LIBRANZAS ---
            lib = None
            if d_idx == 5: lib = "Grupo 1" if s_iso % 2 == 0 else "Grupo 2"; m_d["Grupo 2" if s_iso % 2 == 0 else "Grupo 1"] += 1
            elif d_idx == 6: lib = "Grupo 3" if s_iso % 2 == 0 else "Grupo 4"; m_d["Grupo 4" if s_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                for g in sorted(m_d, key=m_d.get, reverse=True):
                    if m_d[g] > 0 and m_t[g] != "T3": lib = g; m_d[g] -= 1; break

            # --- ASIGNACIÓN ---
            activos = [g for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"] if g != lib]
            hoy_t = {}
            alertas_dia = {}

            for g in activos:
                idx = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"].index(g)
                sug = ["T1", "T2", "T3"][(idx + s_iso) % 3]
                
                error_txt = ""
                if not es_rotacion_valida(m_t[g], sug):
                    error_txt = f"⚠️ Salto descendente: {m_t[g]} -> {sug}"
                
                if m_n[g] >= 6 and sug == "T3": sug = "T1"; error_txt = "🚨 Límite Noches"
                
                hoy_t[g] = sug
                alertas_dia[g] = error_txt

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
                        "Noches_Acum": n_a, "Alerta": alertas_dia.get(g, ""), "Fecha_Raw": pd.to_datetime(fecha)
                    })
                m_t[g], m_n[g] = t_f, n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    # --- RENDERIZADO ---
    if st.session_state.get('malla_generada') is not None:
        df = st.session_state.malla_generada
        df_m = df.drop_duplicates(['Grupo', 'Fecha_Raw'])
        
        # 1. Matriz Colorida (Usando .map en lugar de .applymap)
        st.subheader("📊 Matriz de Turnos")
        mat = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        
        def estilo_turnos(v):
            colors = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {colors.get(v, "#31333F")}; color: white; font-weight: bold; border: 1px solid white'

        st.dataframe(mat.style.map(estilo_turnos), use_container_width=True)

        # 2. Auditoría de Salud
        st.subheader("🔍 Alertas de Rotación")
        alertas = df[df['Alerta'] != ""].drop_duplicates(['Grupo', 'Fecha', 'Alerta'])
        if not alertas.empty:
            st.warning("Se detectaron saltos de turno no recomendados:")
            st.table(alertas[["Fecha", "Grupo", "Alerta"]])
        else:
            st.success("✅ Rotación ascendente perfecta.")

        # 3. Resumen Mensual
        st.subheader("📈 Descansos por Mes")
        res = df[df['Turno'].isin(['DESC', 'COMP'])].drop_duplicates(['Grupo', 'Fecha_Raw'])
        if not res.empty:
            st.table(res.groupby(['Mes', 'Grupo', 'Turno']).size().unstack(fill_value=0))

        # 4. Tabla Detallada
        st.subheader("📋 Detalle Operativo")
        st.dataframe(df[["Fecha", "Nombre", "Cargo", "Cedula", "Hora Inicio", "Hora Fin", "Grupo", "Turno"]], hide_index=True)
