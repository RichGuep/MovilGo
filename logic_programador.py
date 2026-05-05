import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. PERSISTENCIA Y MEMORIA GITHUB ---

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
        repo.update_file("malla_historica.xlsx", "Malla Optimizada V3", output.getvalue(), contents.sha)
        st.success("✅ Histórico sincronizado en GitHub.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

# --- 2. GESTIÓN DE GRUPOS ---

def asignar_grupos_aleatorio(df_cable):
    df = df_cable.copy()
    masters = df[df['Cargo'].str.contains('Master', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_a = df[df['Cargo'].str.contains('Tecnico A', case=False, na=False)].sample(frac=1).to_dict('records')
    tecnicos_b = df[df['Cargo'].str.contains('Tecnico B', case=False, na=False)].sample(frac=1).to_dict('records')
    grupos_finales = []
    num_grupo = 1
    while len(masters) >= 2 and len(tecnicos_a) >= 7 and len(tecnicos_b) >= 3:
        for _ in range(2): p = masters.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(7): p = tecnicos_a.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        for _ in range(3): p = tecnicos_b.pop(); p['Grupo'] = f"Grupo {num_grupo}"; grupos_finales.append(p)
        num_grupo += 1
    for s in (masters + tecnicos_a + tecnicos_b): s['Grupo'] = "Reserva"; grupos_finales.append(s)
    return pd.DataFrame(grupos_finales)

def pantalla_gestion_grupos():
    st.title("👥 Gestión de Grupos")
    if 'df_cable' not in st.session_state:
        try:
            df_full = pd.read_excel("empleados.xlsx")
            df_full.columns = df_full.columns.str.strip()
            st.session_state.df_cable = df_full[df_full['Empresa'].str.contains('Cablemovil', case=False, na=False)].copy()
        except: st.error("Falta empleados.xlsx"); return
    
    if st.button("🎲 Mezclar Grupos"):
        st.session_state.df_cable = asignar_grupos_aleatorio(st.session_state.df_cable)
        st.rerun()
    st.data_editor(st.session_state.df_cable[['Cedula', 'Nombre', 'Cargo', 'Grupo']], use_container_width=True)

# --- 3. PROGRAMADOR CON CONTROL DE DOBLE NOCHE ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Cobertura Única Noche")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    if 'malla_generada' not in st.session_state:
        st.session_state.malla_generada = None

    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Cierre Anterior"):
        estado_ayer_dict = obtener_ultimo_estado_github(repo)
        st.write(estado_ayer_dict)

    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Malla Optimizada"):
        st.cache_data.clear()
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        deudas = {g: 0 for g in grupos_n}
        memoria_t = {g: estado_ayer_dict[g]["u"] for g in grupos_n}
        memoria_n = {g: estado_ayer_dict[g]["n"] for g in grupos_n}
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_fest = fecha in co_h
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

            # 1. Definir Libranza
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

            # 2. Asignación inicial
            activos = [g for g in grupos_n if g != libranza]
            turnos_hoy = {}
            for g in activos:
                idx_g = grupos_n.index(g)
                t_base = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                # Blindaje salud
                if memoria_t[g] == "T3" and t_base in ["T1", "T2"]: t_base = "T3"
                if memoria_n[g] >= 7 and t_base == "T3"]: t_base = "T1"
                turnos_hoy[g] = t_base

            # --- AJUSTE ESTRICTO: NO DOBLE NOCHE ---
            actuales = list(turnos_hoy.values())
            while actuales.count("T3") > 1:
                # Si hay más de un T3, el que NO venga de T3 ayer se mueve a T2 obligatoriamente
                for g_act in activos:
                    if turnos_hoy[g_act] == "T3" and memoria_t[g_act] != "T3" and actuales.count("T3") > 1:
                        turnos_hoy[g_act] = "T2"
                        actuales = list(turnos_hoy.values())
                        break
                # Si AMBOS vienen de T3 ayer (caso raro), movemos al que lleve menos noches
                if actuales.count("T3") > 1:
                    g_mejor = sorted(activos, key=lambda x: memoria_n[x])[0]
                    turnos_hoy[g_mejor] = "T2"
                    actuales = list(turnos_hoy.values())

            # --- GARANTIZAR T1 Y T2 ---
            for t_req in ["T1", "T2", "T3"]:
                if t_req not in turnos_hoy.values():
                    for g_c in activos:
                        if list(turnos_hoy.values()).count(turnos_hoy[g_c]) > 1:
                            if not (memoria_t[g_c] == "T3" and t_req == "T1"):
                                turnos_hoy[g_c] = t_req
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

        st.subheader("🛡️ Validador de Auditoría")
        alertas = []
        for fc in df_m["Fecha_Col"].unique():
            tv = df_m[df_m["Fecha_Col"] == fc]["Turno"].values
            for t in ["T1", "T2", "T3"]:
                if t not in tv: alertas.append(f"{fc} (Falta {t})")
            if list(tv).count("T3") > 1: alertas.append(f"{fc} (Doble Noche)")

        if not alertas: st.success("✅ ¡Malla Perfecta: Sin Doble Noche y Cobertura Total!")
        else: st.error(f"Novedades: {', '.join(alertas)}")
