import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

# --- 1. FUNCIONES DE DATOS (CENTRALIZADAS AQUÍ) ---
def conectar_github():
    if "GITHUB_TOKEN" not in st.secrets: return None
    try:
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def cargar_excel(nombre_archivo):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        contents = repo.get_contents(nombre_archivo)
        df = pd.read_excel(io.BytesIO(contents.decoded_content))
        if 'Fecha_Raw' in df.columns: df['Fecha_Raw'] = pd.to_datetime(df['Fecha_Raw'])
        return df
    except: return pd.DataFrame()

def obtener_estado_inicial(repo):
    df_hist = cargar_excel("malla_historica.xlsx")
    grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    if df_hist.empty: return {g: {"u": "DESC", "n": 0, "d": 0, "sem_d": 0} for g in grupos}
    estado = {}
    for g in grupos:
        regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw')
        if not regs.empty:
            u = regs.iloc[-1]
            estado[g] = {
                "u": u.get('Turno', "DESC"), 
                "n": int(u.get('Noches_Acum', 0)),
                "d": int(u.get('Deuda_Compensatorio', 0)),
                "sem_d": int(u.get('Semana_Deuda', 0))
            }
        else: estado[g] = {"u": "DESC", "n": 0, "d": 0, "sem_d": 0}
    return estado

# --- 2. ESTILOS Y AUDITORÍA ---
def aplicar_estilos_malla(styler, errores_coords):
    colores = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", "DESC": "#d62728", "COMP": "#ff7f0e"}
    def estilo_celda(val, row, col):
        bg = colores.get(val, "transparent")
        color = "white" if val in colores else "black"
        estilo = f"background-color: {bg}; color: {color}; font-weight: bold;"
        if (row, col) in errores_coords:
            estilo += " border: 3px solid #FFFF00 !important; box-shadow: inset 0 0 10px #FFFF00;"
        return estilo
    return styler.apply(lambda df: pd.DataFrame(
        [[estilo_celda(df.iloc[r, c], df.index[r], df.columns[c]) for c in range(len(df.columns))] 
         for r in range(len(df.index))], index=df.index, columns=df.columns), axis=None)

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"] or hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

# --- 3. PANTALLA PRINCIPAL ---
def pantalla_programador():
    st.title("🛡️ Programador Maestro V8.5")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    with st.container(border=True):
        st.subheader("⚙️ Staffing y Descansos de Ley")
        c1, c2 = st.columns([2, 1])
        with c1:
            cd1, cd2 = st.columns(2)
            d_g1 = cd1.selectbox("Descanso G1", dias_semana, index=5)
            d_g2 = cd2.selectbox("Descanso G2", dias_semana, index=5)
            d_g3 = cd1.selectbox("Descanso G3", dias_semana, index=6)
            d_g4 = cd2.selectbox("Descanso G4", dias_semana, index=6)
            map_desc = {"Grupo 1": dias_semana.index(d_g1), "Grupo 2": dias_semana.index(d_g2), 
                        "Grupo 3": dias_semana.index(d_g3), "Grupo 4": dias_semana.index(d_g4)}
        with c2:
            rm = st.number_input("Masters", 1, 10, 3)
            rta = st.number_input("Técnicos A", 1, 20, 7)

    f_ini = st.date_input("Inicio", datetime.now())
    f_fin = st.date_input("Fin", datetime.now() + timedelta(days=28))

    if st.button("🚀 Generar Malla"):
        repo = conectar_github()
        estado = obtener_estado_inicial(repo)
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        mem_t = {g: estado[g]["u"] for g in grupos_n}
        mem_n = {g: estado[g]["n"] for g in grupos_n}
        deudas = {g: estado[g]["d"] for g in grupos_n}
        sem_deuda = {g: estado[g]["sem_d"] for g in grupos_n}

        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha); dia_idx = fecha_dt.weekday()
            n_sem = fecha_dt.isocalendar()[1]; col_name = fecha_dt.strftime('%a %d/%m')
            
            solicitan_descanso = [g for g, d_idx in map_desc.items() if d_idx == dia_idx]
            turnos_hoy = {}

            # Pagar deudas entre semana
            for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                if deudas[g] > 0 and n_sem > sem_deuda[g] and g not in solicitan_descanso:
                    if "COMP" not in turnos_hoy.values():
                        turnos_hoy[g] = "COMP"; deudas[g] -= 1; sem_deuda[g] = 0; break

            # Garantía Cobertura
            activos = [g for g in grupos_n if g not in turnos_hoy and g not in solicitan_descanso]
            while len(activos) < 3 and solicitan_descanso:
                sacrificado = solicitan_descanso.pop(0); deudas[sacrificado] += 1
                sem_deuda[sacrificado] = n_sem; activos.append(sacrificado)
            
            for g in solicitan_descanso: turnos_hoy[g] = "DESC"

            # Asignación Saludable
            t_op = ["T1", "T2", "T3"]; random.shuffle(t_op)
            for g in activos:
                t_sug = next((t for t in t_op if es_cambio_saludable(mem_t[g], t)), "T1")
                if t_sug in t_op: t_op.remove(t_sug)
                turnos_hoy[g] = t_sug

            for g in grupos_n:
                t_f = turnos_hoy.get(g, "T1")
                n_a = mem_n[g] + 1 if t_f == "T3" else 0
                resultados.append({"Grupo": g, "Fecha_Col": col_name, "Turno": t_f, "Fecha_Raw": fecha_dt,
                                   "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g], "Semana_Deuda": sem_deuda[g]})
                mem_t[g] = t_f; mem_n[g] = n_a

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    if st.session_state.get('malla_generada') is not None:
        df_v = st.session_state.malla_generada
        matriz = df_v.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_v["Fecha_Col"].unique())
        st.data_editor(matriz.style.pipe(aplicar_estilos_malla, errores_coords=[]), use_container_width=True)
