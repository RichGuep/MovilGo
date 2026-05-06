import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. PERSISTENCIA Y MEMORIA GITHUB ---

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
        repo.update_file("malla_historica.xlsx", "Malla Richard Fix Final", output.getvalue(), contents.sha)
        st.success("✅ Sincronizado con GitHub.")
    except:
        pass

# --- 2. MOTOR DE SALUD (ASCENDENTE ESTRICTO) ---

def es_cambio_seguro(ayer, hoy):
    """
    Bloquea saltos hacia atrás: T3->T1, T3->T2, T2->T1.
    Garantiza bienestar circadiano.
    """
    if ayer in ["DESC", "COMP", "OFF"]: return True
    if hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia[hoy] >= jerarquia[ayer]

def obtener_horarios(turno):
    h = {"T1": ("05:30", "13:30"), "T2": ("13:30", "21:30"), "T3": ("21:30", "05:30"),
         "DESC": ("OFF", "OFF"), "COMP": ("OFF", "OFF")}
    return h.get(turno, ("-", "-"))

# --- 3. PANTALLA GESTIÓN ---

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos")
    if 'df_cable' not in st.session_state:
        try:
            df = pd.read_excel("empleados.xlsx")
            df.columns = df.columns.str.strip()
            st.session_state.df_cable = df[df['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except: st.error("Falta empleados.xlsx"); return
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 4. PROGRAMADOR MAESTRO ---

def pantalla_programador():
    st.title("📅 Programador Richard - Salud & Reforma 2025")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Cargue empleados en Gestión de Grupos.")
        return

    # Parametrizador de Descansos de Ley
    with st.sidebar.expander("⚙️ Configuración Día de Ley", expanded=True):
        config_desc = {}
        for g in grupos_n:
            def_idx = 0 if g in ["Grupo 1", "Grupo 2"] else 1
            config_desc[g] = st.selectbox(f"Día Ley {g}", ["Sábado", "Domingo"], index=def_idx)

    repo = conectar_github()
    estado_base = obtener_ultimo_estado_github(repo)

    c1, c2 = st.columns(2)
    f_ini = c1.date_input("Inicio", datetime.now())
    f_fin = c2.date_input("Fin", datetime.now() + timedelta(days=30))

    if st.button("🚀 Generar Malla de Bienestar"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        # Corregido: Uso consistente de nombres de variables
        m_t = {g: estado_base[g]["u"] for g in grupos_n}
        m_n = {g: estado_base[g]["n"] for g in grupos_n}
        m_d = {g: estado_base[g]["d"] for g in grupos_n}
        
        for fecha in lista_fechas:
            d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
            
            # 1. Determinar Descanso (Ley / Compensatorio)
            lib = None
            # Descanso de Ley
            for g, dia_pactado in config_desc.items():
                es_dia = (d_idx == 5 and dia_pactado == "Sábado") or (d_idx == 6 and dia_pactado == "Domingo")
                if es_dia:
                    if (g in ["Grupo 1", "Grupo 3"] and s_iso % 2 == 0) or (g in ["Grupo 2", "Grupo 4"] and s_iso % 2 != 0):
                        lib = g
                    else:
                        m_d[g] += 1 # Genera deuda
            
            # Pago de Deuda (Lunes a Viernes)
            if d_idx < 5 and lib is None:
                for g in sorted(m_d, key=m_d.get, reverse=True):
                    if m_d[g] > 0 and m_t[g] != "T3":
                        lib = g; m_d[g] -= 1; break

            # 2. Asignación con Bloqueo de Saltos
            activos = [g for g in grupos_n if g != lib]
            hoy_t = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                t_sug = ["T1", "T2", "T3"][(idx_g + s_iso) % 3]
                
                # Bloqueo: Si el cambio no es ascendente, Inercia (mismo de ayer)
                if not es_cambio_seguro(m_t[g], t_sug):
                    t_sug = m_t[g]
                
                if m_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                hoy_t[g] = t_sug

            # 3. Cobertura Estricta
            for tr in ["T1", "T2", "T3"]:
                if tr not in hoy_t.values():
                    for gf in activos:
                        if list(hoy_t.values()).count(hoy_t[gf]) > 1:
                            if es_cambio_seguro(m_t[gf], tr):
                                hoy_t[gf] = tr; break
            
            # 4. Registro y Memoria
            for g in grupos_n:
                t_f = ("DESC" if d_idx >= 5 else "COMP") if g == lib else hoy_t.get(g, "T1")
                h_i, h_f = obtener_horarios(t_f)
                n_a = m_n[g] + 1 if t_f == "T3" else 0
                
                personal = st.session_state.df_cable[st.session_state.df_cable['Grupo'] == g]
                for _, p in personal.iterrows():
                    resultados.append({
                        "Fecha": fecha.strftime('%Y-%m-%d'), "Nombre": p['Nombre'], "Cargo": p['Cargo'], 
                        "Cedula": p['Cedula'], "Hora Inicio": h_i, "Hora Fin": h_f, "Grupo": g, 
                        "Turno": t_f, "Fecha_Col": f_col, "Mes": fecha.strftime('%B %Y'),
                        "Noches_Acum": n_a, "Deuda": m_d[g], "Fecha_Raw": pd.to_datetime(fecha)
                    })
                m_t[g], m_n[g] = t_f, n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    if st.session_state.get('malla_generada') is not None:
        df = st.session_state.malla_generada
        df_res = df.drop_duplicates(['Grupo', 'Fecha_Raw'])
        
        st.subheader("📊 Matriz Grupal (Control de Bienestar)")
        mat = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        def estilo_t(v):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(v, "#31333F")}; color: white; font-weight: bold; border: 1px solid white'
        st.dataframe(mat.style.map(estilo_t), use_container_width=True)

        st.subheader("📋 Malla Operativa Detallada")
        st.dataframe(df[["Fecha", "Nombre", "Cargo", "Cedula", "Hora Inicio", "Hora Fin", "Grupo", "Turno"]], hide_index=True)
