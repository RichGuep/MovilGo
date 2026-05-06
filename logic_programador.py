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
        st.toast("✅ Sincronizado correctamente", icon="🔄")
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
    st.set_page_config(layout="wide") # Modo ancho para ver todo
    st.title("📅 Programador 24/7 - Panel de Control")
    
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'malla_generada' not in st.session_state:
        st.session_state.malla_generada = None

    repo = conectar_github()
    if not repo: return

    # --- ZONA DE GENERACIÓN (SIDEBAR) ---
    with st.sidebar:
        st.header("⚙️ Generación")
        f_ini = st.date_input("Inicio", datetime.now())
        f_fin = st.date_input("Fin", datetime.now() + timedelta(days=21))
        
        if st.button("🚀 Generar Malla Base", use_container_width=True):
            estado_ayer_dict = obtener_ultimo_estado_github(repo)
            lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
            resultados = []
            
            mem_t = {g: estado_ayer_dict[g]["u"] for g in grupos_n}
            mem_n = {g: estado_ayer_dict[g]["n"] for g in grupos_n}
            deudas = {g: estado_ayer_dict[g]["d"] for g in grupos_n}
            co_h = holidays.Colombia(years=[2024, 2025, 2026])

            for fecha in lista_fechas:
                fecha_dt = pd.to_datetime(fecha)
                dia_idx = fecha_dt.weekday()
                sem_iso = fecha_dt.isocalendar()[1]
                es_fest = fecha_dt in co_h
                col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

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

                activos = [g for g in grupos_n if g != libranza]
                turnos_hoy = {}
                for g in activos:
                    idx_g = grupos_n.index(g)
                    t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                    if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
                    if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
                    turnos_hoy[g] = t_sug

                for tr in ["T1", "T2", "T3"]:
                    if tr not in turnos_hoy.values():
                        for gf in sorted(activos, key=lambda x: (mem_t[x] == "T3")):
                            if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                                if es_cambio_saludable(mem_t[gf], tr):
                                    turnos_hoy[gf] = tr; break
                
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

    # --- CUERPO PRINCIPAL (DOS COLUMNAS) ---
    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        df_res['Fecha_Raw'] = pd.to_datetime(df_res['Fecha_Raw'])
        df_res['Semana'] = df_res['Fecha_Raw'].dt.isocalendar().week
        df_res['Mes'] = df_res['Fecha_Raw'].dt.strftime('%B %Y')

        col_control, col_malla = st.columns([1, 3]) # 1 parte control, 3 partes malla

        with col_control:
            st.subheader("🛠️ Ajuste Rápido")
            
            # --- ANÁLISIS DE NOVEDADES ---
            novedades = []
            for g in grupos_n:
                h = df_res[df_res["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
                for i in range(1, len(h)):
                    if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                        novedades.append({"g": g, "f": h[i]['Fecha_Col'], "t": "Salud"})
            
            df_val = df_res.copy()
            df_val['Es_Descanso'] = df_val['Turno'].isin(['DESC', 'COMP'])
            sem_check = df_val.groupby(['Grupo', 'Semana'], observed=False)['Es_Descanso'].sum()
            errores_ley = sem_check[sem_check < 1].reset_index()
            for _, err in errores_ley.iterrows():
                f_err = df_res[(df_res['Grupo'] == err['Grupo']) & (df_res['Semana'] == err['Semana'])]['Fecha_Col'].iloc[-1]
                novedades.append({"g": err['Grupo'], "f": f_err, "t": "Ley"})

            if novedades:
                st.error("🚨 Novedades")
                for n in novedades:
                    if st.button(f"Fix {n['g']} - {n['f']}", key=f"btn_{n['g']}_{n['f']}", use_container_width=True):
                        st.session_state.temp_grupo = n['g']
                        st.session_state.temp_fecha = n['f']
            
            # Formulario de ajuste
            with st.container(border=True):
                def_g = st.session_state.get('temp_grupo', grupos_n[0])
                def_f = st.session_state.get('temp_fecha', df_res['Fecha_Col'].unique()[0])
                
                g_edit = st.selectbox("Grupo", grupos_n, index=grupos_n.index(def_g))
                f_edit = st.selectbox("Fecha", df_res['Fecha_Col'].unique(), index=list(df_res['Fecha_Col'].unique()).index(def_f))
                t_edit = st.selectbox("Nuevo Turno", ["T1", "T2", "T3", "DESC", "COMP"])
                
                if st.button("💾 Aplicar Cambio", use_container_width=True, type="primary"):
                    mask = (df_res['Grupo'] == g_edit) & (df_res['Fecha_Col'] == f_edit)
                    df_res.loc[mask, 'Turno'] = t_edit
                    st.session_state.malla_generada = df_res
                    guardar_malla_en_historico(df_res)
                    if 'temp_grupo' in st.session_state: del st.session_state.temp_grupo
                    if 'temp_fecha' in st.session_state: del st.session_state.temp_fecha
                    st.rerun()

        with col_malla:
            st.subheader("📊 Malla Actual")
            matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
            matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())
            st.dataframe(matriz.style.map(color_t), use_container_width=True, height=400)

            with st.expander("⚖️ Cumplimiento Legal (Días libres)"):
                t1, t2 = st.tabs(["Semanal (Mín 1)", "Mensual"])
                with t1:
                    sem_v = df_val.groupby(['Grupo', 'Semana'], observed=False)['Es_Descanso'].sum().unstack(fill_value=0)
                    st.dataframe(sem_v.style.map(lambda x: 'background-color: #702020' if x < 1 else 'background-color: #205020'))
                with t2:
                    mes_v = df_val.groupby(['Grupo', 'Mes'], observed=False)['Es_Descanso'].sum().unstack(fill_value=0)
                    st.dataframe(mes_v)

if __name__ == "__main__":
    pantalla_programador()
