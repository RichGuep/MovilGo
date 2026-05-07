import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

# --- 1. GESTIÓN DE DATOS GITHUB ---
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except:
        return None

def obtener_estado_inicial(repo):
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df = pd.read_excel(io.BytesIO(contents.decoded_content))
        df['Fecha_Raw'] = pd.to_datetime(df['Fecha_Raw'])
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            regs = df[df['Grupo'] == g].sort_values('Fecha_Raw')
            if not regs.empty:
                u = regs.iloc[-1]
                estado[g] = {
                    "u": u['Turno'], 
                    "d": int(u.get('Deuda_Compensatorio', 0)),
                    "sem_deuda": int(u.get('Semana_Deuda', 0))
                }
            else:
                estado[g] = {"u": "DESC", "d": 0, "sem_deuda": 0}
        return estado
    except:
        return {g: {"u": "DESC", "d": 0, "sem_deuda": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

def guardar_malla_github(df):
    repo = conectar_github()
    if not repo: return
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        repo.update_file("malla_historica.xlsx", "Malla V6 - Compensatorios Inmediatos", output.getvalue(), contents.sha)
    except:
        repo.create_file("malla_historica.xlsx", "Malla Inicial", output.getvalue())

# --- 2. MOTOR DE PROGRAMACIÓN ---
def pantalla_programador():
    st.title("🛡️ Programador Maestro: Cobertura y Equidad")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    # --- PARAMETRIZACIÓN ---
    with st.container(border=True):
        st.subheader("📋 Parámetros de Staffing y Descansos")
        c1, c2, c3 = st.columns(3)
        req_m = c1.number_input("Masters (Líderes)", 1, 10, 3)
        req_ta = c2.number_input("Técnicos A", 1, 20, 7)
        req_tb = c3.number_input("Técnicos B", 1, 20, 2)
        
        st.write("**Asignación de Descanso Fijo:**")
        cols_d = st.columns(4)
        conf_desc = {}
        for i, g in enumerate(grupos_n):
            conf_desc[g] = cols_d[i].selectbox(f"Descanso {g}", dias_semana, index=(5 if i < 2 else 6))

    f_ini = st.date_input("Fecha Inicio", datetime.now())
    f_fin = st.date_input("Fecha Fin", datetime.now() + timedelta(days=28))

    if st.button("🚀 Generar Malla Inteligente"):
        repo = conectar_github()
        estado = obtener_estado_inicial(repo)
        
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        deudas = {g: estado[g]["d"] for g in grupos_n}
        sem_deuda = {g: estado[g]["sem_deuda"] for g in grupos_n}
        mem_t = {g: estado[g]["u"] for g in grupos_n}
        
        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha)
            dia_idx = fecha_dt.weekday()
            n_sem = fecha_dt.isocalendar()[1]
            col_name = fecha_dt.strftime('%a %d/%m')
            
            turnos_hoy = {}
            # 1. Candidatos a descanso fijo hoy
            quieren_fijo = [g for g, d in conf_desc.items() if dias_semana.index(d) == dia_idx]
            
            # 2. Prioridad: Pagar deudas de la semana pasada (Compensatorios)
            deudores_urgentes = [g for g in grupos_n if deudas[g] > 0 and n_sem > sem_deuda[g]]
            
            # Intentar asignar compensatorios (máximo 1 por día para no vaciar turnos)
            compensado_hoy = None
            for g in deudores_urgentes:
                if g not in quieren_fijo:
                    compensado_hoy = g
                    turnos_hoy[g] = "COMP"
                    deudas[g] -= 1
                    sem_deuda[g] = 0
                    break

            # 3. Validar Cobertura (Mínimo 3 activos para T1, T2, T3)
            # Quienes no están compensando y no quieren fijo son activos por defecto
            activos_seguros = [g for g in grupos_n if g not in turnos_hoy and g not in quieren_fijo]
            
            # Si solo hay 2 o menos activos, alguien que quería descansar debe trabajar (genera deuda)
            while len(activos_seguros) < 3 and quieren_fijo:
                sacrificado = quieren_fijo.pop(0)
                deudas[sacrificado] += 1
                sem_deuda[sacrificado] = n_sem
                activos_seguros.append(sacrificado)
            
            # Asignar DESC a los que pudieron librar el fijo
            for g in quieren_fijo:
                turnos_hoy[g] = "DESC"

            # 4. Asignar T1, T2, T3 a los activos
            turnos_op = ["T1", "T2", "T3"]
            random.shuffle(turnos_op)
            for g in activos_seguros:
                if turnos_op:
                    turnos_hoy[g] = turnos_op.pop(0)
                else:
                    turnos_hoy[g] = "T1" # En caso de grupo flotante (4to grupo)

            for g in grupos_n:
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": turnos_hoy[g],
                    "Fecha_Raw": fecha_dt, "Deuda_Compensatorio": deudas[g],
                    "Semana_Deuda": sem_deuda[g], "M_Req": req_m, "TA_Req": req_ta, "TB_Req": req_tb
                })
                mem_t[g] = turnos_hoy[g]

        df_final = pd.DataFrame(resultados)
        st.session_state.malla_generada = df_final
        guardar_malla_github(df_final)
        st.rerun()

    # --- VISUALIZACIÓN ---
    if st.session_state.get('malla_generada') is not None:
        df = st.session_state.malla_generada
        matriz = df.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
        
        st.subheader("✍️ Vista Maestro de Turnos")
        st.dataframe(matriz.style.map(lambda x: 'background-color: #d62728; color: white' if x in ['DESC', 'COMP'] else ''), use_container_width=True)
        
        st.subheader("⚖️ Contador de Equidad (Mensual)")
        resumen = df.groupby('Grupo')['Turno'].value_counts().unstack(fill_value=0)
        st.table(resumen)
