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
            st.error("❌ Token GITHUB_TOKEN no configurado en secrets.")
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error de conexión GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
    """Obtiene el último turno y deudas para dar continuidad a la salud laboral."""
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df_hist = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_hist['Fecha_Raw'] = pd.to_datetime(df_hist['Fecha_Raw'])
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw', ascending=True)
            if not regs.empty:
                u = regs.iloc[-1] # El registro más reciente en el tiempo
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
            # Combinamos y evitamos duplicados priorizando la versión nueva
            df_final = pd.concat([df_previo, df_nueva]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
        except:
            df_final = df_nueva

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        contents = repo.get_contents("malla_historica.xlsx")
        repo.update_file("malla_historica.xlsx", "Actualización Malla Parametrizada", output.getvalue(), contents.sha)
        st.success("✅ Datos sincronizados correctamente.")
    except Exception as e:
        st.error(f"Error al sincronizar: {e}")

# --- 2. LÓGICA DE SALUD ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", "DESC": "#d62728", "COMP": "#ff7f0e"}
    return f'background-color: {c.get(val, "#ffffff")}; color: white; font-weight: bold; text-align: center;'

# --- 3. PANTALLA PRINCIPAL DEL PROGRAMADOR ---

def pantalla_programador():
    st.title("📅 Programador Maestro MovilGo")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    # --- CONFIGURACIÓN DE DESCANSOS (Parametrización) ---
    with st.sidebar:
        st.header("⚙️ Reglas de Negocio")
        dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        desc1_nom = st.selectbox("Día Descanso A (G1/G2)", dias_semana, index=5) # Default Sábado
        desc2_nom = st.selectbox("Día Descanso B (G3/G4)", dias_semana, index=6) # Default Domingo
        
        idx_desc1 = dias_semana.index(desc1_nom)
        idx_desc2 = dias_semana.index(desc2_nom)

    # --- FILTRO DE FECHAS ---
    st.subheader("1. Definir Periodo de Programación")
    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Fecha Inicio", datetime.now())
    f_fin = c_f2.date_input("Fecha Fin", datetime.now() + timedelta(days=14))

    if st.button("🚀 Generar Malla Inteligente"):
        # Limpiar caché para forzar nuevos datos
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

            libranza = None
            # Aplicación de descansos parametrizados
            if dia_idx == idx_desc1:
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
            elif dia_idx == idx_desc2:
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
            else:
                # Cobro de compensatorios en días ordinarios
                for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                    if deudas[g] > 0 and mem_t[g] != "T3":
                        libranza = g; deudas[g] -= 1; break

            activos = [g for g in grupos_n if g != libranza]
            turnos_hoy = {}
            
            # Asignación de turnos base
            for g in activos:
                idx_g = grupos_n.index(g)
                # Rotación basada en semana y grupo
                t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                
                # Validación de salud (no saltos hacia atrás)
                if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
                # Máximo 6 noches
                if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                
                turnos_hoy[g] = t_sug

            # Motor de Cobertura: Asegurar que T1, T2 y T3 estén cubiertos
            for tr in ["T1", "T2", "T3"]:
                if tr not in turnos_hoy.values() and activos:
                    # Buscamos quién puede cambiar sin romper reglas de salud
                    for gf in activos:
                        if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                            if es_cambio_saludable(mem_t[gf], tr):
                                turnos_hoy[gf] = tr; break
            
            for g in grupos_n:
                t_f = ("DESC" if dia_idx in [idx_desc1, idx_desc2] else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                    "Fecha_Raw": fecha_dt, "Noches_Acum": n_a,
                    "Deuda_Compensatorio": deudas[g]
                })
                mem_t[g] = t_f; mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    # --- VISUALIZACIÓN Y EDICIÓN ---
    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        df_res['Fecha_Raw'] = pd.to_datetime(df_res['Fecha_Raw'])
        
        # Filtro visual para el rango seleccionado
        df_res = df_res[(df_res['Fecha_Raw'].dt.date >= f_ini) & (df_res['Fecha_Raw'].dt.date <= f_fin)]
        
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())

        st.subheader("✍️ Editor Manual (Vista del Rango Seleccionado)")
        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"]) for c in matriz.columns}
        matriz_editada = st.data_editor(matriz, column_config=config_col, use_container_width=True)

        if st.button("💾 Guardar Cambios Manuales"):
            df_man = matriz_editada.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = df_res.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            guardar_malla_en_historico(df_final)
            st.session_state.malla_generada = df_final
            st.rerun()

        st.subheader("📊 Mapa de Calor de Turnos")
        st.dataframe(matriz_editada.style.map(color_t), use_container_width=True)

if __name__ == "__main__":
    pantalla_programador()
