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
    # ... (Mantener inicialización de fechas y conexión)

    if st.button("🚀 Generar Malla Equitativa"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        # 1. CARGA DE MEMORIA HISTÓRICA (Crucial para la equidad)
        # Traemos no solo el último turno, sino el conteo total acumulado si es posible
        # Por ahora, usamos el estado_ayer_dict que ya tienes
        mem_t = {g: estado_ayer_dict[g]["u"] for g in grupos_n}
        mem_n = {g: estado_ayer_dict[g]["n"] for g in grupos_n}
        deudas = {g: estado_ayer_dict[g]["d"] for g in grupos_n}
        
        # Diccionario de carga histórica para balancear (T3 pesa más, T1 menos)
        # Esto asegura que si el Grupo 1 hizo muchas noches el mes pasado, este mes descanse más
        carga_acumulada = {g: 0 for g in grupos_n} 
        
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha)
            dia_idx = fecha_dt.weekday()
            sem_iso = fecha_dt.isocalendar()[1]
            es_fest = fecha_dt in co_h
            col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

            # --- A. LÓGICA DE LIBRANZAS (Igual) ---
            libranza = None
            if dia_idx == 5:
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6:
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                # Prioridad de compensatorio al que tenga más deuda
                posibles_comp = sorted([g for g in grupos_n if g != libranza], 
                                     key=lambda x: deudas[x], reverse=True)
                if deudas[posibles_comp[0]] > 0 and mem_t[posibles_comp[0]] != "T3":
                    libranza = posibles_comp[0]
                    deudas[libranza] -= 1

            activos = [g for g in grupos_n if g != libranza]
            
            # --- B. ASIGNACIÓN POR EQUIDAD DE CARGA ---
            # Definimos los turnos a cubrir
            turnos_disponibles = ["T3", "T2", "T1"]
            turnos_hoy = {}

            # 1. Primero asignamos el T3 (el más pesado) al que menos carga lleve
            # 2. Luego el T2 y finalmente T1
            for t_necesario in turnos_disponibles:
                # Ordenamos activos por carga acumulada (menor carga primero)
                # Y filtramos los que ya tienen turno asignado hoy
                candidatos = [g for g in activos if g not in turnos_hoy]
                
                # Ordenar candidatos: 1. Menos carga, 2. Que sea saludable
                candidatos = sorted(candidatos, key=lambda x: (carga_acumulada[x], x))
                
                asignado = False
                for c in candidatos:
                    if es_cambio_saludable(mem_t[c], t_necesario):
                        # Control estricto de noches (Max 6)
                        if not (t_necesario == "T3" and mem_n[c] >= 6):
                            turnos_hoy[c] = t_necesario
                            # Aumentamos el peso: T3 vale 3 puntos, T2 vale 2, T1 vale 1
                            carga_acumulada[c] += {"T3": 3, "T2": 2, "T1": 1}[t_necesario]
                            asignado = True
                            break
                
                # Si nadie podía por salud (bloqueo), forzamos T1 al que falte
                if not asignado and candidatos:
                    c = candidatos[0]
                    turnos_hoy[c] = "T1"
                    carga_acumulada[c] += 1

            # --- C. PERSISTENCIA ---
            for g in grupos_n:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                    "Fecha_Raw": fecha_dt, "Noches_Acum": n_a,
                    "Deuda_Compensatorio": deudas[g]
                })
                mem_t[g] = t_f
                mem_n[g] = n_a

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
