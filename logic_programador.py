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
            registros = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw')
            if not registros.empty:
                ultimo_reg = registros.iloc[-1]
                estado[g] = {
                    "ultimo_turno": ultimo_reg['Turno'],
                    "noches_seguidas": int(ultimo_reg.get('Noches_Acum', 0)) if ultimo_reg['Turno'] == "T3" else 0
                }
            else:
                estado[g] = {"ultimo_turno": "DESC", "noches_seguidas": 0}
        return estado
    except:
        return {g: {"ultimo_turno": "DESC", "noches_seguidas": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

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
        repo.update_file("malla_historica.xlsx", "Corrección Cobertura Total", output.getvalue(), contents.sha)
        st.success("✅ Malla sincronizada correctamente.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

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

# --- 3. PROGRAMADOR CON COBERTURA BLINDADA ---

def pantalla_programador():
    st.title("📅 Programador 24/7 - Cobertura Obligatoria")
    grupos_nombres = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    
    repo = conectar_github()
    if not repo: return

    with st.expander("👁️ Cierre Anterior"):
        estado_ayer_dict = obtener_ultimo_estado_github(repo)
        st.write(estado_ayer_dict)

    c_f1, c_f2 = st.columns(2)
    f_inicio = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=21))

    if st.button("🚀 Generar Malla Sin Huecos"):
        st.cache_data.clear()
        lista_fechas = [f_inicio + timedelta(days=x) for x in range((f_fin - f_inicio).days + 1)]
        resultados = []
        deudas = {g: 0 for g in grupos_nombres}
        memoria_turno = {g: estado_ayer_dict[g]["ultimo_turno"] for g in grupos_nombres}
        noches_seguidas = {g: estado_ayer_dict[g]["noches_seguidas"] for g in grupos_nombres}
        co_holidays = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            dia_idx = fecha.weekday()
            sem_iso = fecha.isocalendar()[1]
            es_festivo = fecha in co_holidays
            col_name = f"{fecha.strftime('%a %d/%m')}{' 🇨🇴' if es_festivo else ''}"

            # 1. Definir Libranza (Solo 1 grupo descansa)
            libranza = None
            if dia_idx == 5: # Sáb
                libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
                deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
            elif dia_idx == 6: # Dom
                libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
                deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
            else:
                for g in sorted(grupos_nombres, key=lambda x: (noches_seguidas[x], deudas[x]), reverse=True):
                    if deudas[g] > 0 and memoria_turno[g] != "T3":
                        libranza = g; deudas[g] -= 1; break

            # 2. Asignación Inicial de Turnos
            activos = [g for g in grupos_nombres if g != libranza]
            turnos_dia = {}
            for g in activos:
                idx_g = grupos_nombres.index(g)
                # Rotación base
                t_base = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
                # Protección T3 -> T1/T2
                if memoria_turno[g] == "T3" and t_base in ["T1", "T2"]: t_base = "T3"
                # Límite noches
                if noches_seguidas[g] >= 7 and t_base == "T3": t_base = "T1"
                turnos_dia[g] = t_base

            # --- MOTOR DE COBERTURA ESTRICTA ---
            for t_obligatorio in ["T1", "T2", "T3"]:
                if t_obligatorio not in turnos_dia.values():
                    # Si falta un turno, buscamos a un grupo que esté duplicando otro turno
                    for g_candidato in sorted(activos, key=lambda x: noches_seguidas[x]):
                        # Contamos cuántos grupos están en el turno actual de este candidato
                        turno_actual_candidato = turnos_dia[g_candidato]
                        if list(turnos_dia.values()).count(turno_actual_candidato) > 1:
                            # Solo cambiamos si no es un riesgo de salud (T3 -> T1/T2)
                            if not (memoria_turno[g_candidato] == "T3" and t_obligatorio in ["T1", "T2"]):
                                turnos_dia[g_candidato] = t_obligatorio
                                break

            # 3. Guardar día
            for g in grupos_nombres:
                t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_dia.get(g, "T1")
                n_acum = noches_seguidas[g] + 1 if t_f == "T3" else 0
                noches_seguidas[g] = n_acum
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                    "Fecha_Raw": pd.to_datetime(fecha), "Noches_Acum": n_acum
                })
                memoria_turno[g] = t_f

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

        st.subheader("🛡️ Auditoría de Cobertura")
        alertas = []
        for fc in df_m["Fecha_Col"].unique():
            tv = df_m[df_m["Fecha_Col"] == fc]["Turno"].values
            for t in ["T1", "T2", "T3"]:
                if t not in tv: alertas.append(f"Falta {t} el {fc}")
        
        if not alertas: st.success("✅ ¡Operación Blindada! T1, T2 y T3 cubiertos todos los días.")
        else: st.error(f"⚠️ Huecos detectados: {', '.join(alertas[:5])}...")
