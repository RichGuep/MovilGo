import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. PERSISTENCIA EN GITHUB ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token GITHUB_TOKEN no configurado.")
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

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
                estado[g] = {"u": u['Turno'], "n": int(u.get('Noches_Acum', 0)), "d": int(u.get('Deuda_Compensatorio', 0))}
            else:
                estado[g] = {"u": "DESC", "n": 0, "d": 0}
        return estado
    except:
        return {g: {"u": "DESC", "n": 0, "d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

def guardar_malla(df):
    repo = conectar_github()
    if not repo: return
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        contents = repo.get_contents("malla_historica.xlsx")
        repo.update_file("malla_historica.xlsx", "Update Malla Staffing", output.getvalue(), contents.sha)
        st.success("✅ Sincronizado con GitHub")
    except:
        repo.create_file("malla_historica.xlsx", "Crear Malla", output.getvalue())

# --- 2. MOTOR DE LOGICA ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"] or hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def pantalla_programador():
    st.title("🛡️ Programador de Cobertura Garantizada")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    # --- PARAMETRIZACIÓN POR ROL ---
    with st.container(border=True):
        st.subheader("👥 Configuración de Staffing por Turno")
        col1, col2, col3 = st.columns(3)
        req_master = col1.number_input("Masters (Líderes)", 1, 10, 3)
        req_tecA = col2.number_input("Técnicos A", 1, 20, 7)
        req_tecB = col3.number_input("Técnicos B", 1, 20, 2)
        total_p_turno = req_master + req_tecA + req_tecB
        st.caption(f"Total requerido por turno: {total_p_turno} personas. (Total día: {total_p_turno * 3})")

        st.subheader("📅 Descansos Fijos Solicitados")
        cols = st.columns(4)
        mapa_descansos = {}
        for i, g in enumerate(grupos_n):
            mapa_descansos[g] = dias_semana.index(cols[i].selectbox(f"Descanso {g}", dias_semana, index=(5 if i<2 else 6)))

    # --- GENERADOR ---
    c_f1, c_f2 = st.columns(2)
    f_ini = c_f1.date_input("Inicio", datetime.now())
    f_fin = c_f2.date_input("Fin", datetime.now() + timedelta(days=14))

    if st.button("🚀 Generar Malla y Validar Cobertura"):
        repo = conectar_github()
        estado = obtener_ultimo_estado_github(repo)
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        mem_t = {g: estado[g]["u"] for g in grupos_n}
        deudas = {g: estado[g]["d"] for g in grupos_n}
        co_h = holidays.Colombia(years=[2024, 2025, 2026])

        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha)
            dia_idx = fecha_dt.weekday()
            sem_iso = fecha_dt.isocalendar()[1]
            es_fest = fecha_dt in co_h
            col_name = f"{fecha_dt.strftime('%a %d/%m')}"

            # 1. Intentar dar descanso
            grupos_que_quieren_descanso = [g for g, d_idx in mapa_descansos.items() if d_idx == dia_idx]
            
            # 2. Obligación: Siempre debe haber 3 grupos activos para cubrir T1, T2, T3
            # Si más de 1 grupo quiere descansar, el sistema obliga a trabajar a uno.
            if len(grupos_que_quieren_descanso) > 1:
                # Se queda a trabajar el que tenga menos deuda de descansos
                grupos_que_quieren_descanso.sort(key=lambda x: deudas[x])
                sacrificado = grupos_que_quieren_descanso.pop(0)
                deudas[sacrificado] += 1 # Se le debe un día por trabajar en su descanso

            libranza = grupos_que_quieren_descanso[0] if grupos_que_quieren_descanso else None
            activos = [g for g in grupos_n if g != libranza]
            
            # 3. Asignación de Turnos (Garantizando T1, T2, T3)
            turnos_disponibles = ["T1", "T2", "T3"]
            turnos_hoy = {}
            
            # Intentar rotación saludable
            for g in activos:
                idx_g = grupos_n.index(g)
                t_sug = turnos_disponibles[(idx_g + sem_iso) % 3]
                turnos_hoy[g] = t_sug
            
            # Asegurar que no se repitan turnos y se cubran los 3
            usados = list(turnos_hoy.values())
            for i, t_falta in enumerate(turnos_disponibles):
                if t_falta not in usados:
                    # Si falta un turno, reasignamos al grupo que tenga duplicado
                    for g_act in activos:
                        if list(turnos_hoy.values()).count(turnos_hoy[g_act]) > 1:
                            turnos_hoy[g_act] = t_falta; break

            for g in grupos_n:
                t_final = "DESC" if g == libranza else turnos_hoy.get(g, "T1")
                # Si trabajó un festivo y no es su descanso, suma deuda
                if es_fest and t_final not in ["DESC", "COMP"]:
                    deudas[g] += 1

                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": t_final, "Fecha_Raw": fecha_dt,
                    "Deuda_Compensatorio": deudas[g], "M_Req": req_master, "TA_Req": req_tecA, "TB_Req": req_tecB
                })
                mem_t[g] = t_final

        st.session_state.malla_generada = pd.DataFrame(resultados)
        guardar_malla(st.session_state.malla_generada)
        st.rerun()

    # --- VISUALIZACIÓN ---
    if st.session_state.get('malla_generada') is not None:
        df = st.session_state.malla_generada
        matriz = df.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        st.subheader("✍️ Malla Generada (T1, T2, T3 Garantizados)")
        st.write("El sistema ha priorizado la cobertura sobre los descansos donde fue necesario.")
        st.dataframe(matriz, use_container_width=True)
        
        # Métricas de Equidad
        st.subheader("⚖️ Balance de Deuda de Descansos (Compensatorios)")
        cols_m = st.columns(4)
        for i, g in enumerate(grupos_n):
            valor = df[df['Grupo'] == g]['Deuda_Compensatorio'].iloc[-1]
            cols_m[i].metric(f"Pendientes {g}", f"{valor} días")

# --- ESTILOS DE COLOR ---
def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", "DESC": "#d62728", "COMP": "#ff7f0e"}
    return f'background-color: {c.get(val, "#ffffff")}; color: white; font-weight: bold; text-align: center;'
