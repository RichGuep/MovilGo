import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. PERSISTENCIA Y MEMORIA GITHUB ---

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
                    "trab": int(u.get('Dias_Seguidos', 0))
                }
            else:
                estado[g] = {"u": "T1", "n": 0, "d": 0, "trab": 0}
        return estado
    except:
        return {g: {"u": "T1", "n": 0, "d": 0, "trab": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

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
        repo.update_file("malla_historica.xlsx", "Malla Richard Master V10", output.getvalue(), contents.sha)
        st.success("✅ Datos sincronizados en GitHub.")
    except: pass

# --- 2. MOTOR DE SALUD Y REGLAS ---

def es_salto_valido(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]: return True
    niveles = {"T1": 1, "T2": 2, "T3": 3}
    return niveles[hoy] >= niveles[ayer]

def obtener_horarios(turno):
    h = {"T1": ("05:30", "13:30"), "T2": ("13:30", "21:30"), "T3": ("21:30", "05:30")}
    return h.get(turno, ("OFF", "OFF"))

# --- 3. PROGRAMADOR MAESTRO ---

def pantalla_programador():
    st.title("📅 Programador Maestro Richard - 24/7")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Cargue empleados en Gestión de Grupos.")
        return

    # Inicialización de estados de sesión
    if 'df_editable' not in st.session_state: st.session_state.df_editable = None
    if 'df_plano' not in st.session_state: st.session_state.df_plano = None

    repo = conectar_github()
    estado_base = obtener_ultimo_estado_github(repo)

    with st.sidebar:
        st.header("⚙️ Parametrización")
        f_ini = st.date_input("Inicio", datetime.now())
        f_fin = st.date_input("Fin", datetime.now() + timedelta(days=31))
        
        config_ley = {}
        for g in grupos_n:
            def_idx = 0 if g in ["Grupo 1", "Grupo 2"] else 1
            config_ley[g] = st.selectbox(f"Día Ley {g}", ["Sábado", "Domingo"], index=def_idx)

        if st.button("🚀 Generar Nueva Proyección"):
            st.cache_data.clear()
            lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
            res = []
            
            m_t = {g: estado_base[g]["u"] for g in grupos_n}
            m_d = {g: estado_base[g]["d"] for g in grupos_n}
            m_n = {g: estado_base[g]["n"] for g in grupos_n}
            m_trab = {g: estado_base[g]["trab"] for g in grupos_n}

            for fecha in lista_fechas:
                d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
                lib = None
                
                # 1. Descanso de Ley
                for g, dia_ley in config_ley.items():
                    es_dia = (d_idx == 5 and dia_ley == "Sábado") or (d_idx == 6 and dia_ley == "Domingo")
                    if es_dia:
                        if (g in ["Grupo 1", "Grupo 3"] and s_iso % 2 == 0) or (g in ["Grupo 2", "Grupo 4"] and s_iso % 2 != 0):
                            lib = g
                        else: m_d[g] += 1

                # 2. Pago de Compensatorios Inmediato
                if d_idx < 5 and lib is None:
                    prioridad = sorted(m_d, key=lambda x: (m_d[x], m_trab[x]), reverse=True)
                    for g in prioridad:
                        if (m_d[g] > 0 or m_trab[g] > 5) and m_t[g] != "T3":
                            lib = g; m_d[g] = max(0, m_d[g]-1); break

                # 3. Asignación con Blindaje T3->T1
                activos = [g for g in grupos_n if g != lib]
                hoy_t = {}
                for g in activos:
                    idx = grupos_n.index(g)
                    sug = ["T1", "T2", "T3"][(idx + s_iso) % 3]
                    
                    if not es_salto_valido(m_t[g], sug): sug = m_t[g] # Inercia de salud
                    if m_n[g] >= 6 and sug == "T3": sug = "T1"
                    hoy_t[g] = sug

                # 4. Registro y Auditoría
                for g in grupos_n:
                    es_lib = (g == lib)
                    t_f = ("DESC" if d_idx >= 5 else "COMP") if es_lib else hoy_t.get(g, "T1")
                    m_trab[g] = 0 if es_lib else m_trab[g] + 1
                    n_a = m_n[g] + 1 if t_f == "T3" else 0
                    
                    res.append({
                        "Grupo": g, "Fecha_Col": f_col, "Turno": t_f, "Fecha_Raw": pd.to_datetime(fecha),
                        "Mes": fecha.strftime('%B %Y'), "Semana": f"Sem {s_iso}",
                        "Días_Seguidos": m_trab[g], "Deuda": m_d[g], "Noches_Acum": n_a
                    })
                    m_t[g], m_n[g] = t_f, n_a

            df_plano = pd.DataFrame(res)
            st.session_state.df_plano = df_plano
            st.session_state.df_editable = df_plano.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
            st.rerun()

    # --- RENDERIZADO Y EDICIÓN ---
    if st.session_state.df_editable is not None:
        st.subheader("📝 Matriz Editable (Haz clic para corregir)")
        df_editado = st.data_editor(
            st.session_state.df_editable,
            column_config={c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"]) for c in st.session_state.df_editable.columns},
            use_container_width=True
        )

        if st.button("💾 Guardar y Procesar Estadísticas"):
            # Re-mapeo para guardar histórico
            final_rows = []
            for g in df_editado.index:
                for f_col in df_editado.columns:
                    turno = df_editado.loc[g, f_col]
                    orig = st.session_state.df_plano[(st.session_state.df_plano['Grupo']==g) & (st.session_state.df_plano['Fecha_Col']==f_col)].iloc[0]
                    final_rows.append({
                        "Grupo": g, "Fecha_Raw": orig['Fecha_Raw'], "Turno": turno, "Fecha_Col": f_col,
                        "Mes": orig['Mes'], "Semana": orig['Semana'], "Deuda": orig['Deuda'], "Dias_Seguidos": orig['Días_Seguidos']
                    })
            df_save = pd.DataFrame(final_rows)
            guardar_malla_en_historico(df_save)
            st.session_state.df_plano = df_save
            st.rerun()

        # --- ESTADÍSTICAS Y VALIDACIÓN ---
        st.divider()
        st.subheader("📊 Estadísticas de Comportamiento")
        
        tab1, tab2, tab3 = st.tabs(["📅 Por Mes", "📋 Por Semana", "⚠️ Validador de Salud"])
        
        with tab1:
            st.write("**Conteo de Descansos Totales (DESC + COMP) por Mes:**")
            df_st = st.session_state.df_plano
            stats_mes = df_st[df_st['Turno'].isin(['DESC', 'COMP'])].groupby(['Mes', 'Grupo']).size().unstack(fill_value=0)
            st.dataframe(stats_mes, use_container_width=True)

        with tab2:
            st.write("**Distribución de Turnos por Semana:**")
            stats_sem = df_st.groupby(['Semana', 'Grupo', 'Turno']).size().unstack(fill_value=0)
            st.dataframe(stats_sem, use_container_width=True)

        with tab3:
            st.write("**Alertas de Fatiga y Saltos Prohibidos:**")
            alertas = []
            for g in grupos_n:
                grupo_data = df_st[df_st['Grupo'] == g].sort_values('Fecha_Raw').to_dict('records')
                for i in range(1, len(grupo_data)):
                    # Validar Salto T3 a T1
                    if not es_salto_valido(grupo_data[i-1]['Turno'], grupo_data[i]['Turno']):
                        alertas.append(f"❌ {g}: Salto Prohibido el {grupo_data[i]['Fecha_Col']} ({grupo_data[i-1]['Turno']} -> {grupo_data[i]['Turno']})")
                    # Validar Días Seguidos
                    if grupo_data[i]['Dias_Seguidos'] > 6:
                        alertas.append(f"🚨 {g}: Más de 6 días sin descanso el {grupo_data[i]['Fecha_Col']}")
            
            if alertas: 
                for a in alertas[:10]: st.error(a)
            else: st.success("✅ Todo en orden: Rotación y Descansos cumplen la norma.")

# --- 4. GESTIÓN DE GRUPOS ---
def pantalla_gestion_grupos():
    st.title("👥 Gestión de Personal")
    if 'df_cable' not in st.session_state:
        try:
            df = pd.read_excel("empleados.xlsx")
            st.session_state.df_cable = df[df['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except: st.error("Falta empleados.xlsx"); return
    
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)
