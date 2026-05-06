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
        st.toast("✅ Sincronizado en GitHub", icon="🔄")
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

# --- 3. FUNCIÓN PRINCIPAL (PANTALLA) ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Gestión Integral")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'malla_generada' not in st.session_state:
        st.session_state.malla_generada = None

    repo = conectar_github()
    if not repo: return

    # --- PANEL LATERAL DE GENERACIÓN ---
    with st.sidebar:
        st.header("⚙️ Parámetros")
        f_ini = st.date_input("Inicio", datetime.now())
        f_fin = st.date_input("Fin", datetime.now() + timedelta(days=28))
        
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

                # Lógica original de Libranza
                libranza = None
                if dia_idx == 5:
                    libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                    deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
                elif dia_idx == 6:
                    libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                    deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
                else:
                    for g in sorted(grupos_n, key=lambda x: deudas[g], reverse=True):
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

                # Lógica original de Cobertura
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

    # --- VISUALIZACIÓN Y EDICIÓN ---
    if st.session_state.malla_generada is not None:
        df_res = st.session_state.malla_generada.copy()
        # Asegurar columnas de tiempo para validadores
        df_res['Fecha_Raw'] = pd.to_datetime(df_res['Fecha_Raw'])
        df_res['Semana'] = df_res['Fecha_Raw'].dt.isocalendar().week
        df_res['Mes'] = df_res['Fecha_Raw'].dt.strftime('%B %Y')

        # 1. Popover de Edición Rápida (Ajuste Rápido)
        with st.popover("✏️ Ajuste Rápido de Turno", use_container_width=True):
            st.write("Cambia un turno específico:")
            c1, c2, c3 = st.columns(3)
            g_sel = c1.selectbox("Grupo", grupos_n)
            f_sel = c2.selectbox("Día", df_res['Fecha_Col'].unique())
            t_sel = c3.selectbox("Nuevo Turno", ["T1", "T2", "T3", "DESC", "COMP"])
            
            if st.button("Confirmar Cambio", use_container_width=True):
                mask = (df_res['Grupo'] == g_sel) & (df_res['Fecha_Col'] == f_sel)
                df_res.loc[mask, 'Turno'] = t_sel
                st.session_state.malla_generada = df_res
                guardar_malla_en_historico(df_res)
                st.rerun()

        # 2. Matriz Principal con Colores
        matriz = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_res["Fecha_Col"].unique())
        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        # 3. Validador Legal
        with st.expander("⚖️ Validador de Descansos de Ley", expanded=True):
            df_val = df_res.copy()
            df_val['Es_Descanso'] = df_val['Turno'].isin(['DESC', 'COMP'])
            col_a, col_b = st.columns(2)
            
            with col_a:
                st.caption("Días libres por Semana (Mín 1)")
                sem_v = df_val.groupby(['Grupo', 'Semana'], observed=False)['Es_Descanso'].sum().unstack(fill_value=0)
                st.dataframe(sem_v.style.map(lambda x: 'background-color: #702020' if x < 1 else 'background-color: #205020'))
            
            with col_b:
                st.caption("Acumulado Mensual")
                mes_v = df_val.groupby(['Grupo', 'Mes'], observed=False)['Es_Descanso'].sum().unstack(fill_value=0)
                st.dataframe(mes_v)

        # 4. Alertas de Salud (Localizador)
        st.divider()
        alertas = []
        for g in grupos_n:
            h = df_res[df_res["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
            for i in range(1, len(h)):
                if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                    alertas.append(f"⚠️ **{g}**: Salto de {h[i-1]['Turno']} a {h[i]['Turno']} el día {h[i]['Fecha_Col']}")
        
        if alertas:
            st.error("Novedades de Salud detectadas:")
            for a in alertas[:5]: st.write(a)
        else:
            st.success("✅ Rotación de salud perfecta.")

# IMPORTANTE: Cambia el nombre aquí si tu app.py llama a pantalla_gestion_grupos
def pantalla_gestion_grupos():
    pantalla_programador()
