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
        repo.update_file("malla_historica.xlsx", "Actualización Malla Manual/Auto", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado en GitHub.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 2. LÓGICA DE SALUD Y ROTACIÓN ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"]: return True
    if hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia[hoy] >= jerarquia[ayer]

# --- 3. PANTALLA PRINCIPAL ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Ajuste Manual Habilitado")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'malla_generada' not in st.session_state:
        st.session_state.malla_generada = None

    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Ver Cierre Anterior (Estado Actual)"):
        estado_ayer_dict = obtener_ultimo_estado_github(repo)
        st.write(estado_ayer_dict)

    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin (Proyección)", datetime.now() + timedelta(days=14))

    if st.button("🚀 Generar Nueva Malla"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        mem_t = {g: estado_ayer_dict[g]["u"] for g in grupos_n}
        mem_n = {g: estado_ayer_dict[g]["n"] for g in grupos_n}
        deudas = {g: estado_ayer_dict[g]["d"] for g in grupos_n}
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_fest = fecha in co_h
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

            # 1. Libranza
            libranza = None
            if dia_idx == 5:
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6:
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                    if deudas[g] > 0 and mem_t[g] != "T3":
                        libranza = g; deudas[g] -= 1; break

            # 2. Asignación Inicial
            activos = [g for g in grupos_n if g != libranza]
            turnos_hoy = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                if not es_cambio_saludable(mem_t[g], t_sug):
                    t_sug = mem_t[g]
                if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                turnos_hoy[g] = t_sug

            # 3. Cobertura y Refuerzos
            for tr in ["T1", "T2", "T3"]:
                if tr not in turnos_hoy.values():
                    for gf in sorted(activos, key=lambda x: (mem_t[x] == "T3")):
                        if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                            if es_cambio_saludable(mem_t[gf], tr):
                                turnos_hoy[gf] = tr; break
            
            actuales = list(turnos_hoy.values())
            while actuales.count("T3") > 1:
                for g_n in activos:
                    if turnos_hoy[g_n] == "T3" and (mem_t[g_n] != "T3" or actuales.count("T3") > 1):
                        turnos_hoy[g_n] = "T2"
                        actuales = list(turnos_hoy.values()); break
            
            for g_f in activos:
                if turnos_hoy[g_f] == "T1" and actuales.count("T1") > 1:
                    turnos_hoy[g_f] = "T2"
                    actuales = list(turnos_hoy.values())

            # 4. Registro
            for g in grupos_n:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                    "Fecha_Raw": pd.to_datetime(fecha), "Noches_Acum": n_a,
                    "Deuda_Compensatorio": deudas[g]
                })
                mem_t[g] = t_f; mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    # --- SECCIÓN DE EDICIÓN MANUAL ---
    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada
        
        # Crear matriz para el editor
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())

        st.subheader("✍️ Editor de Malla (Ajustes Manuales)")
        st.caption("Modifica los turnos directamente en la tabla y presiona 'Guardar Cambios'.")

        # Configuración de columnas para que sean desplegables
        config_columnas = {
            col: st.column_config.SelectboxColumn(
                options=["T1", "T2", "T3", "DESC", "COMP"],
                required=True
            ) for col in matriz.columns
        }

        matriz_editada = st.data_editor(
            matriz,
            column_config=config_columnas,
            use_container_width=True,
            key="editor_interactivo"
        )

        if st.button("💾 Guardar y Sincronizar Cambios"):
            # Convertir la matriz de nuevo al formato largo
            df_editado_melt = matriz_editada.reset_index().melt(
                id_vars="Grupo", 
                var_name="Fecha_Col", 
                value_name="Turno"
            )
            
            # Actualizar el DataFrame original preservando datos ocultos (Raw, Acum, etc.)
            df_final = df_res.copy()
            for _, fila in df_editado_melt.iterrows():
                mask = (df_final['Grupo'] == fila['Grupo']) & (df_final['Fecha_Col'] == fila['Fecha_Col'])
                df_final.loc[mask, 'Turno'] = fila['Turno']
            
            st.session_state.malla_generada = df_final
            guardar_malla_en_historico(df_final)
            st.rerun()

        # --- VALIDACIÓN DE SALUD ---
        st.divider()
        st.subheader("🔍 Validador de Salud Richard")
        alertas = []
        for g in grupos_n:
            h = df_res[df_res["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
            for i in range(1, len(h)):
                if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                    alertas.append(f"⚠️ {g} ({h[i]['Fecha_Col']}): Salto no saludable de {h[i-1]['Turno']} a {h[i]['Turno']}")
        
        if not alertas:
            st.success("✅ La malla actual cumple con la Rotación Ascendente Perfecta.")
        else:
            for a in alertas[:8]: # Mostrar las primeras 8 alertas
                st.warning(a)

if __name__ == "__main__":
    pantalla_programador()
