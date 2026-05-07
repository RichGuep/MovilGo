import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. CONEXIÓN Y PERSISTENCIA ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token GITHUB_TOKEN no configurado.")
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
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
            df_previo['Fecha_Raw'] = pd.to_datetime(df_previo['Fecha_Raw'])
            df_final = pd.concat([df_previo, df_nueva]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
        except:
            df_final = df_nueva
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        contents = repo.get_contents("malla_historica.xlsx")
        repo.update_file("malla_historica.xlsx", "Malla Parametrizada V5", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado en GitHub.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 2. LÓGICA DE SALUD Y FORMATO ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", "DESC": "#d62728", "COMP": "#ff7f0e"}
    return f'background-color: {c.get(val, "#ffffff")}; color: white; font-weight: bold; text-align: center;'

# --- 3. PANTALLA PRINCIPAL ---

def pantalla_programador():
    st.title("📅 Programador Maestro MovilGo")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    # --- BLOQUE DE PARÁMETROS PRINCIPALES ---
    with st.container(border=True):
        st.subheader("⚙️ Configuración de Reglas y Staffing")
        
        col_desc, col_staff = st.columns([2, 1])
        
        with col_desc:
            st.write("**Descansos Independientes por Grupo:**")
            cd1, cd2 = st.columns(2)
            d_g1 = cd1.selectbox("Descanso Grupo 1", dias_semana, index=5)
            d_g2 = cd2.selectbox("Descanso Grupo 2", dias_semana, index=5)
            d_g3 = cd1.selectbox("Descanso Grupo 3", dias_semana, index=6)
            d_g4 = cd2.selectbox("Descanso Grupo 4", dias_semana, index=6)
            
            mapa_descansos = {
                "Grupo 1": dias_semana.index(d_g1),
                "Grupo 2": dias_semana.index(d_g2),
                "Grupo 3": dias_semana.index(d_g3),
                "Grupo 4": dias_semana.index(d_g4)
            }

        with col_staff:
            st.write("**Personal Requerido por Turno:**")
            req_lider = st.number_input("Líderes", min_value=1, value=1)
            req_tecnico = st.number_input("Técnicos", min_value=1, value=3)
            req_aux = st.number_input("Auxiliares", min_value=0, value=2)

    # --- RANGO DE FECHAS ---
    st.subheader("1. Definir Periodo")
    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=14))

    if st.button("🚀 Generar Malla con Parámetros Seleccionados"):
        repo = conectar_github()
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

            # Identificar quién libra hoy según el mapa dinámico
            libranza_hoy = [g for g, d_idx in mapa_descansos.items() if d_idx == dia_idx]
            
            activos = [g for g in grupos_n if g not in libranza_hoy]
            turnos_hoy = {}
            
            for g in activos:
                idx_g = grupos_n.index(g)
                t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
                if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                turnos_hoy[g] = t_sug

            # Motor Cobertura
            for tr in ["T1", "T2", "T3"]:
                if tr not in turnos_hoy.values() and activos:
                    for gf in activos:
                        if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                            if es_cambio_saludable(mem_t[gf], tr):
                                turnos_hoy[gf] = tr; break
            
            for g in grupos_n:
                t_f = "DESC" if g in libranza_hoy else turnos_hoy.get(g, "T1")
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                    "Fecha_Raw": fecha_dt, "Noches_Acum": n_a,
                    "Req_Lider": req_lider, "Req_Tecnico": req_tecnico, "Req_Aux": req_aux
                })
                mem_t[g] = t_f; mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    # --- EDITOR ---
    if st.session_state.get('malla_generada') is not None:
        df_res = st.session_state.malla_generada.copy()
        df_res['Fecha_Raw'] = pd.to_datetime(df_res['Fecha_Raw'])
        
        # Filtro de rango visual
        df_res = df_res[(df_res['Fecha_Raw'].dt.date >= f_ini) & (df_res['Fecha_Raw'].dt.date <= f_fin)]
        
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())

        st.subheader("✍️ Editor de Turnos")
        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"]) for c in matriz.columns}
        matriz_editada = st.data_editor(matriz, column_config=config_col, use_container_width=True)

        if st.button("💾 Guardar Ajustes Manuales"):
            df_man = matriz_editada.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = df_res.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            guardar_malla_en_historico(df_final)
            st.session_state.malla_generada = df_final
            st.rerun()

        st.dataframe(matriz_editada.style.map(color_t), use_container_width=True)
