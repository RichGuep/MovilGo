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
        repo.update_file("malla_historica.xlsx", "Malla Saludable Richard V4", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado en GitHub.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 2. LÓGICA DE SALUD Y FORMATO ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"]: return True
    if hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
    return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

# --- 3. PROGRAMADOR ---
def pantalla_programador():
    st.title("📅 Programador 24/7 - Rotación Uniforme")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'malla_generada' not in st.session_state:
        st.session_state.malla_generada = None

    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Ver Cierre Anterior"):
        estado_ayer_dict = obtener_ultimo_estado_github(repo)
        st.write(estado_ayer_dict)

    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=28))

    if st.button("🚀 Generar Malla Equitativa"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        # 1. ESTADO INICIAL
        mem_n = {g: estado_ayer_dict[g]["n"] for g in grupos_n}
        deudas = {g: estado_ayer_dict[g]["d"] for g in grupos_n}
        
        # Secuencia uniforme: T1 -> T2 -> T3
        secuencia_trabajo = ["T1", "T2", "T3"]
        
        # Mapeo para saber en qué parte de la rueda de trabajo quedó cada grupo
        def get_work_idx(u):
            if u == "T1": return 1 # El siguiente es T2
            if u == "T2": return 2 # El siguiente es T3
            return 0 # El siguiente es T1 (si venía de T3 o DESC)
            
        indices_trabajo = {g: get_work_idx(estado_ayer_dict[g]["u"]) for g in grupos_n}
        
        # Desfase inicial para que no todos empiecen en T1 (si es la primera vez)
        if len(set(indices_trabajo.values())) == 1 and all(v == 0 for v in indices_trabajo.values()):
            indices_trabajo = {"Grupo 1": 0, "Grupo 2": 1, "Grupo 3": 2, "Grupo 4": 0}

        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha)
            dia_idx = fecha_dt.weekday()
            sem_iso = fecha_dt.isocalendar()[1]
            es_fest = fecha_dt in co_h
            col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

            # --- A. DEFINIR LIBRANZAS DE LEY (Fines de semana) ---
            libranza_ley = None
            if dia_idx == 5: # Sábado
                libranza_ley = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6: # Domingo
                libranza_ley = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1

            # --- B. ASIGNACIÓN DE TURNOS ---
            turnos_hoy = {}
            # Priorizamos dar el COMP al que más deba
            grupos_prioridad = sorted(grupos_n, key=lambda x: deudas[x], reverse=True)

            for g in grupos_prioridad:
                # 1. Si es su descanso de Ley
                if g == libranza_ley:
                    turnos_hoy[g] = "DESC"
                
                # 2. Si tiene deuda de compensatorio
                # (Y no permitimos más de 2 descansos totales para no dejar solo el turno)
                elif deudas[g] > 0 and list(turnos_hoy.values()).count("COMP") < 1:
                    turnos_hoy[g] = "COMP"
                    deudas[g] -= 1
                
                # 3. Si trabaja, sigue la secuencia T1-T2-T3
                else:
                    idx = indices_trabajo[g]
                    t_asignado = secuencia_trabajo[idx]
                    
                    # Protección Salud: Si toca T3 pero ya lleva 6 noches, forzamos un descanso extra
                    if t_asignado == "T3" and mem_n[g] >= 6:
                        turnos_hoy[g] = "COMP"
                        # No avanzamos el índice para que haga la noche al volver
                    else:
                        turnos_hoy[g] = t_asignado
                        # Avanzamos la rueda solo porque trabajó
                        indices_trabajo[g] = (idx + 1) % 3

            # --- C. GUARDADO Y MEMORIA ---
            for g in grupos_n:
                t_f = turnos_hoy.get(g, "T1")
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                    "Fecha_Raw": fecha_dt, "Noches_Acum": n_a,
                    "Deuda_Compensatorio": deudas[g]
                })
                mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

            # --- C. GUARDADO ---
            for g in grupos_n:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
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
        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    if st.session_state.malla_generada is not None:
        # --- ASEGURAR COLUMNAS DE TIEMPO (Evita el KeyError) ---
        df_res = st.session_state.malla_generada.copy()
        df_res['Fecha_Raw'] = pd.to_datetime(df_res['Fecha_Raw'])
        df_res['Semana'] = df_res['Fecha_Raw'].dt.isocalendar().week
        df_res['Mes'] = df_res['Fecha_Raw'].dt.strftime('%B %Y')

        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())

        st.subheader("✍️ Ajustes Manuales")
        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"]) for c in matriz.columns}
        matriz_editada = st.data_editor(matriz, column_config=config_col, use_container_width=True, key="edit_vFinal")

        if st.button("💾 Guardar Cambios"):
            df_man = matriz_editada.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            # Unir con los datos originales para no perder Fecha_Raw
            df_final = df_res.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            st.session_state.malla_generada = df_final
            guardar_malla_en_historico(df_final)
            st.rerun()

        st.subheader("📊 Vista de Colores")
        st.dataframe(matriz_editada.style.map(color_t), use_container_width=True)

        # --- VALIDACIÓN DE LEY ---
        st.divider()
        st.subheader("⚖️ Validador de Descansos de Ley")
        
        df_val = df_res.copy()
        df_val['Es_Descanso'] = df_val['Turno'].isin(['DESC', 'COMP'])
        
        t1, t2, t3 = st.tabs(["Resumen por Grupo", "Detalle Semanal", "Detalle Mensual"])
        
        with t1:
            resumen = df_val.groupby('Grupo')['Es_Descanso'].sum().reset_index()
            resumen.columns = ['Grupo', 'Total Libres']
            st.table(resumen)
            
        with t2:
            # Aquí es donde fallaba: nos aseguramos que 'Semana' existe
            sem_val = df_val.groupby(['Grupo', 'Semana'], observed=False)['Es_Descanso'].sum().unstack(fill_value=0)
            st.write("Días libres por Semana (Mínimo legal: 1)")
            st.dataframe(sem_val.style.map(lambda x: 'color: #ff4b4b' if x < 1 else 'color: #2ca02c'))

        with t3:
            mes_val = df_val.groupby(['Grupo', 'Mes'], observed=False)['Es_Descanso'].sum().unstack(fill_value=0)
            st.write("Días libres acumulados por Mes")
            st.dataframe(mes_val)

        # --- NAVEGADOR DE NOVEDADES ---
        st.divider()
        st.subheader("🔍 Localizador de Novedades de Salud")
        alertas_lista = []
        for g in grupos_n:
            h = df_res[df_res["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
            for i in range(1, len(h)):
                if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                    alertas_lista.append({
                        "msg": f"⚠️ {g}: Salto {h[i-1]['Turno']} a {h[i]['Turno']} en {h[i]['Fecha_Col']}", 
                        "grupo": g, 
                        "fecha": h[i]['Fecha_Col']
                    })
        
        if alertas_lista:
            sel = st.selectbox("Ubicar error:", options=[a["msg"] for a in alertas_lista])
            info = next(item for item in alertas_lista if item["msg"] == sel)
            st.warning(f"Error detectado en: **{info['grupo']}** el día **{info['fecha']}**")
        else:
            st.success("✅ Rotación de salud perfecta.")

if __name__ == "__main__":
    pantalla_programador()
