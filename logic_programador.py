import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

# --- 1. CONFIGURACIÓN DE ESTILOS ---
def aplicar_estilos_malla(styler):
    """Aplica colores institucionales a la malla."""
    colores = {
        "T1": "background-color: #1f77b4; color: white;",
        "T2": "background-color: #2ca02c; color: white;",
        "T3": "background-color: #4d4d4d; color: white;",
        "DESC": "background-color: #d62728; color: white;",
        "COMP": "background-color: #ff7f0e; color: white;"
    }
    return styler.map(lambda x: colores.get(x, "background-color: transparent; color: inherit"))

# --- 2. PERSISTENCIA ---
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def obtener_ultimo_estado(repo):
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
                    "sem_d": int(u.get('Semana_Deuda', 0))
                }
            else:
                estado[g] = {"u": "DESC", "d": 0, "sem_d": 0}
        return estado
    except:
        return {g: {"u": "DESC", "d": 0, "sem_d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

# --- 3. PANTALLA PRINCIPAL ---
def pantalla_programador():
    st.title("🛡️ Programador de Cobertura Flexible")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    with st.container(border=True):
        st.subheader("⚙️ Reglas de Descanso y Staffing")
        c_desc, c_staff = st.columns([2, 1])
        with c_desc:
            st.write("**Día de Descanso Fijo Solicitado:**")
            cd1, cd2 = st.columns(2)
            d_g1 = cd1.selectbox("Grupo 1", dias_semana, index=5)
            d_g2 = cd2.selectbox("Grupo 2", dias_semana, index=5)
            d_g3 = cd1.selectbox("Grupo 3", dias_semana, index=6)
            d_g4 = cd2.selectbox("Grupo 4", dias_semana, index=6)
            map_desc = {
                "Grupo 1": dias_semana.index(d_g1), "Grupo 2": dias_semana.index(d_g2),
                "Grupo 3": dias_semana.index(d_g3), "Grupo 4": dias_semana.index(d_g4)
            }
        with c_staff:
            st.write("**Requerimiento Mínimo:**")
            rm = st.number_input("Masters", 1, 10, 3)
            rta = st.number_input("Téc A", 1, 20, 7)
            rtb = st.number_input("Téc B", 1, 20, 2)

    f_ini = st.date_input("Inicio", datetime.now())
    f_fin = st.date_input("Fin", datetime.now() + timedelta(days=28))

    if st.button("🚀 Generar Malla Optimizada"):
        repo = conectar_github()
        estado = obtener_ultimo_estado(repo)
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        deudas = {g: estado[g]["d"] for g in grupos_n}
        sem_deuda = {g: estado[g]["sem_d"] for g in grupos_n}
        
        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha)
            dia_idx = fecha_dt.weekday()
            n_sem = fecha_dt.isocalendar()[1]
            col_name = fecha_dt.strftime('%a %d/%m')
            
            turnos_hoy = {}
            # 1. ¿Quién solicita descanso hoy?
            solicitan_descanso = [g for g, d_idx in map_desc.items() if d_idx == dia_idx]
            
            # 2. Prioridad: Pagar deudas de compensatorio (Si hay deuda de semanas pasadas)
            # Se paga de Lunes a Viernes para no chocar con descansos fijos
            if dia_idx < 5:
                for g in grupos_n:
                    if deudas[g] > 0 and n_sem > sem_deuda[g] and g not in turnos_hoy:
                        if len([v for v in turnos_hoy.values() if v == "COMP"]) < 1: # 1 compensado max por día
                            turnos_hoy[g] = "COMP"
                            deudas[g] -= 1
                            sem_deuda[g] = 0

            # 3. Validar Cobertura (Necesitamos 3 grupos activos para T1, T2, T3)
            # Si los que piden descanso + los que están compensando dejan < 3 grupos...
            activos_seguros = [g for g in grupos_n if g not in turnos_hoy and g not in solicitan_descanso]
            
            while len(activos_seguros) < 3 and solicitan_descanso:
                # Alguien que quería descansar debe trabajar
                sacrificado = solicitan_descanso.pop(0)
                deudas[sacrificado] += 1
                sem_deuda[sacrificado] = n_sem
                activos_seguros.append(sacrificado)
            
            for g in solicitan_descanso: turnos_hoy[g] = "DESC"
            
            # 4. Asignar turnos operativos
            t_pool = ["T1", "T2", "T3"]
            random.shuffle(t_pool)
            for g in activos_seguros:
                turnos_hoy[g] = t_pool.pop(0) if t_pool else "T1"

            for g in grupos_n:
                resultados.append({
                    "Grupo": g, "Fecha_Col": col_name, "Turno": turnos_hoy[g],
                    "Fecha_Raw": fecha_dt, "Deuda_Compensatorio": deudas[g],
                    "Semana_Deuda": sem_deuda[g], "M_Req": rm, "TA_Req": rta, "TB_Req": rtb
                })

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    if st.session_state.get('malla_generada') is not None:
        df_v = st.session_state.malla_generada.copy()
        matriz = df_v.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_v["Fecha_Col"].unique())
        
        st.subheader("✍️ Editor de Turnos")
        st.data_editor(matriz.style.pipe(aplicar_estilos_malla), use_container_width=True)
        
        # Métricas de Auditoría
        st.divider()
        st.subheader("📊 Auditoría de Cobertura y Deudas")
        m1, m2 = st.columns(2)
        m1.metric("Compensatorios Pendientes", int(df_v['Deuda_Compensatorio'].iloc[-1]))
        
        # Validar saltos T3 -> T1
        st.write("**Alertas de Salud:**")
        # (Lógica de auditoría aquí...)

        # EJECUCIÓN AUTOMÁTICA DE AUDITORÍA
        auditar_malla(df_v)

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", "DESC": "#d62728", "COMP": "#ff7f0e"}
    return f'background-color: {c.get(val, "#ffffff")}; color: white; font-weight: bold; text-align: center;'
