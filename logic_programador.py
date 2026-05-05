import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. PERSISTENCIA GITHUB ---

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
            registros = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw')
            if not registros.empty:
                u = registros.iloc[-1]
                estado[g] = {"u": u['Turno'], "n": int(u.get('Noches_Acum', 0)) if u['Turno'] == "T3" else 0}
            else:
                estado[g] = {"u": "DESC", "n": 0}
        return estado
    except:
        return {g: {"u": "DESC", "n": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

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
        repo.update_file("malla_historica.xlsx", "Cobertura Blindada V2", output.getvalue(), contents.sha)
        st.success("✅ Histórico actualizado.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- 2. GESTIÓN DE GRUPOS ---

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos")
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            st.session_state.df_cable = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except: st.error("Falta empleados.xlsx"); return
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 3. PROGRAMADOR CON COBERTURA RECURSIVA ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Cobertura Garantizada")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Ver cierre anterior"):
        estado_ayer_base = obtener_ultimo_estado_github(repo)
        st.write(estado_ayer_base)

    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Malla Estricta"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        deudas = {g: 0 for g in grupos_n}
        memoria_t = {g: estado_ayer_base[g]["u"] for g in grupos_n}
        memoria_n = {g: estado_ayer_base[g]["n"] for g in grupos_n}
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_fest = fecha in co_h
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_fest_col := es_fest else ''}"

            # 1. Libranza
            libranza = None
            if dia_idx == 5:
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6:
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                for g in sorted(grupos_n, key=lambda x: (memoria_n[x], deudas[x]), reverse=True):
                    if deudas[g] > 0 and memoria_t[g] != "T3":
                        libranza = g; deudas[g] -= 1; break

            # 2. Asignación Activos
            activos = [g for g in grupos_n if g != libranza]
            turnos_hoy = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                t_base = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                # Blindaje salud inicial
                if memoria_t[g] == "T3" and t_base in ["T1", "T2"]: t_base = "T3"
                if memoria_n[g] >= 7 and t_base == "T3": t_base = "T1"
                turnos_hoy[g] = t_base

            # --- MOTOR DE COBERTURA ESTRICTA (RECURSIVO) ---
            for t_req in ["T1", "T2", "T3"]:
                if t_req not in turnos_hoy.values():
                    # Buscamos quién está repetido para moverlo
                    # Priorizamos mover al que NO viene de T3 ayer
                    candidatos = sorted(activos, key=lambda x: (memoria_t[x] == "T3"))
                    for g_c in candidatos:
                        turno_actual = turnos_hoy[g_c]
                        if list(turnos_hoy.values()).count(turno_actual) > 1:
                            # Validar que el movimiento a t_req no sea un salto mortal (T3 -> T1)
                            if not (memoria_t[g_c] == "T3" and t_req in ["T1", "T2"]):
                                turnos_hoy[g_c] = t_req
                                break
                    
                    # Si después del filtro anterior el turno sigue faltando (casos críticos)
                    # Forzamos la cobertura: la ciudad no puede quedar sin turno
                    if t_req not in turnos_hoy.values():
                        for g_f in activos:
                            if list(turnos_hoy.values()).count(turnos_hoy[g_f]) > 1:
                                turnos_hoy[g_f] = t_req # Movimiento forzoso
                                break

            # 3. Registro
            for g in grupos_n:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
                n_a = memoria_n[g] + 1 if t_f == "T3" else 0
                memoria_n[g] = n_a
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                    "Fecha_Raw": pd.to_datetime(fecha), "Noches_Acum": n_a
                })
                memoria_t[g] = t_f

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla_en_historico(st.session_state.malla_generada)
        st.rerun()

    if st.session_state.malla_generada is not None:
        df_m = st.session_state.malla_generada
        matriz = df_m.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        matriz = matriz.reindex(columns=df_m["Fecha_Col"].unique())
        
        def color_t(val):
            c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
            return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold; border: 1px solid #444'

        st.dataframe(matriz.style.map(color_t), use_container_width=True)

        st.subheader("🛡️ Auditoría Operativa")
        errores = []
        for fc in df_m["Fecha_Col"].unique():
            tv = df_m[df_m["Fecha_Col"] == fc]["Turno"].values
            for t in ["T1", "T2", "T3"]:
                if t not in tv: errores.append(f"Día {fc} falta {t}")
        
        if not errores: st.success("✅ Cobertura Total Garantizada: T1, T2 y T3 cubiertos.")
        else: st.error(f"⚠️ Huecos: {', '.join(errores)}")
