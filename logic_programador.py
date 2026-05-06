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
            st.error("❌ Token GITHUB_TOKEN no configurado.")
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
        repo.update_file("malla_historica.xlsx", "Actualización Malla Richard V5", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado en GitHub.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 2. LÓGICA DE SALUD Y FUNCIONES APOYO ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"]: return True
    if hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def obtener_horarios(turno):
    h = {"T1": ("05:30", "13:30"), "T2": ("13:30", "21:30"), "T3": ("21:30", "05:30"), 
         "DESC": ("OFF", "OFF"), "COMP": ("OFF", "OFF")}
    return h.get(turno, ("-", "-"))

# --- 3. PANTALLA: GESTIÓN DE GRUPOS ---

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos")
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            st.session_state.df_cable = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except:
            st.error("Falta empleados.xlsx")
            return
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 4. PANTALLA: PROGRAMADOR MAESTRO ---

def pantalla_programador():
    st.title("📅 Programador Richard - Matriz Interactiva")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    # Inicialización de estados
    if 'df_editable' not in st.session_state: st.session_state.df_editable = None
    if 'df_full_data' not in st.session_state: st.session_state.df_full_data = None

    if 'df_cable' not in st.session_state:
        st.warning("⚠️ Primero cargue los grupos en Gestión de Grupos.")
        return

    repo = conectar_github()
    if not repo: return
    estado_base = obtener_ultimo_estado_github(repo)

    with st.sidebar:
        st.header("⚙️ Parámetros")
        f_ini = st.date_input("Inicio", datetime.now())
        f_fin = st.date_input("Fin (Proyección)", datetime.now() + timedelta(days=31))
        
        if st.button("🚀 Generar Nueva Proyección"):
            st.cache_data.clear()
            lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
            resultados = []
            
            m_t = {g: estado_base[g]["u"] for g in grupos_n}
            m_n = {g: estado_base[g]["n"] for g in grupos_n}
            m_d = {g: estado_base[g]["d"] for g in grupos_n}
            co_h = holidays.Colombia(years=[2024, 2025, 2026])

            for fecha in lista_fechas:
                d_idx, s_iso, f_col = fecha.weekday(), fecha.isocalendar()[1], fecha.strftime('%a %d/%m')
                lib = None
                
                # 1. Libranza Ciclo
                if d_idx == 5:
                    lib = "Grupo 1" if s_iso % 2 == 0 else "Grupo 2"
                    m_d["Grupo 2" if s_iso % 2 == 0 else "Grupo 1"] += 1
                elif d_idx == 6:
                    lib = "Grupo 3" if s_iso % 2 == 0 else "Grupo 4"
                    m_d["Grupo 4" if s_iso % 2 == 0 else "Grupo 3"] += 1
                else:
                    for g in sorted(grupos_n, key=lambda x: m_d[x], reverse=True):
                        if m_d[g] > 0 and m_t[g] != "T3":
                            lib = g; m_d[g] -= 1; break

                # 2. Turnos con Inercia
                activos = [g for g in grupos_n if g != lib]
                hoy_t = {}
                for g in activos:
                    idx_g = grupos_n.index(g)
                    sug = ["T1", "T2", "T3"][(idx_g + s_iso) % 3]
                    if not es_cambio_saludable(m_t[g], sug): sug = m_t[g]
                    if m_n[g] >= 6 and sug == "T3": sug = "T1"
                    hoy_t[g] = sug

                # 3. Cobertura Estricta
                for tr in ["T1", "T2", "T3"]:
                    if tr not in hoy_t.values():
                        for gf in sorted(activos, key=lambda x: m_n[x]):
                            if list(hoy_t.values()).count(hoy_t[gf]) > 1:
                                if es_cambio_saludable(m_t[gf], tr):
                                    hoy_t[gf] = tr; break

                for g in grupos_n:
                    t_f = ("DESC" if d_idx >= 5 else "COMP") if g == lib else hoy_t.get(g, "T1")
                    n_a = m_n[g] + 1 if t_f == "T3" else 0
                    resultados.append({
                        "Grupo": g, "Fecha_Col": f_col, "Turno": t_f, "Fecha_Raw": pd.to_datetime(fecha),
                        "Noches_Acum": n_a, "Deuda": m_d[g], "Mes": fecha.strftime('%B %Y'),
                        "Semana": f"Sem {s_iso}"
                    })
                    m_t[g], m_n[g] = t_f, n_a

            df_gen = pd.DataFrame(resultados)
            st.session_state.df_full_data = df_gen
            st.session_state.df_editable = df_gen.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
            st.rerun()

    # --- MATRIZ EDITABLE ---
    if st.session_state.df_editable is not None:
        st.subheader("📝 Edición de Turnos")
        st.info("Haz clic en cualquier celda para corregir un turno manualmente.")
        
        # Estilo de colores para el editor
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold'

        df_editado = st.data_editor(
            st.session_state.df_editable,
            column_config={col: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"]) for col in st.session_state.df_editable.columns},
            use_container_width=True
        )

        if st.button("💾 Guardar Cambios y Procesar Métricas"):
            # Re-procesar datos planos para estadísticas y guardado
            filas_finales = []
            for g in df_editado.index:
                for f_col in df_editado.columns:
                    turno = df_editado.loc[g, f_col]
                    # Recuperar metadatos del original
                    orig = st.session_state.df_full_data[
                        (st.session_state.df_full_data['Grupo'] == g) & 
                        (st.session_state.df_full_data['Fecha_Col'] == f_col)
                    ].iloc[0]
                    
                    filas_finales.append({
                        "Grupo": g, "Fecha_Col": f_col, "Turno": turno, "Fecha_Raw": orig['Fecha_Raw'],
                        "Mes": orig['Mes'], "Semana": orig['Semana'], "Deuda": orig['Deuda'], 
                        "Noches_Acum": orig['Noches_Acum']
                    })
            
            df_final = pd.DataFrame(filas_finales)
            st.session_state.df_full_data = df_final
            guardar_malla_en_historico(df_final)
            st.rerun()

        # --- SECCIÓN DE MÉTRICAS Y VALIDACIÓN ---
        st.divider()
        st.subheader("📊 Auditoría Richard: Métricas de Comportamiento")
        
        tab_mes, tab_sem, tab_salud = st.tabs(["📅 Mensual", "📋 Semanal", "⚖️ Validador de Salud"])
        
        with tab_mes:
            st.write("**Descansos Totales (DESC + COMP) por Grupo al Mes:**")
            df_m = st.session_state.df_full_data
            metricas_mes = df_m[df_m['Turno'].isin(['DESC', 'COMP'])].groupby(['Mes', 'Grupo']).size().unstack(fill_value=0)
            st.dataframe(metricas_mes, use_container_width=True)

        with tab_sem:
            st.write("**Distribución de Turnos por Semana:**")
            metricas_sem = df_m.groupby(['Semana', 'Grupo', 'Turno']).size().unstack(fill_value=0)
            st.dataframe(metricas_sem, use_container_width=True)

        with tab_salud:
            alertas = []
            for g in grupos_n:
                h = df_m[df_m['Grupo'] == g].sort_values('Fecha_Raw').to_dict('records')
                for i in range(1, len(h)):
                    if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                        alertas.append(f"⚠️ {g}: Salto Prohibido el {h[i]['Fecha_Col']} ({h[i-1]['Turno']} -> {h[i]['Turno']})")
            
            if alertas:
                for a in alertas: st.error(a)
            else:
                st.success("✅ Rotación 100% Saludable detectada.")
