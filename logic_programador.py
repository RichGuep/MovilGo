import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

# --- 1. CONFIGURACIÓN DE ESTILOS (CORREGIDO PARA PANDAS 2.x) ---
def aplicar_estilos_malla(styler):
    """Aplica el código de colores oficial usando el nuevo método .map() de Pandas."""
    colores = {
        "T1": "background-color: #1f77b4; color: white;",
        "T2": "background-color: #2ca02c; color: white;",
        "T3": "background-color: #4d4d4d; color: white;",
        "DESC": "background-color: #d62728; color: white;",
        "COMP": "background-color: #ff7f0e; color: white;"
    }
    # Se cambió .applymap por .map para evitar el AttributeError
    return styler.map(lambda x: colores.get(x, "background-color: transparent; color: inherit"))

# --- 2. PERSISTENCIA GITHUB ---
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

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
        repo.update_file("malla_historica.xlsx", "Malla Actualizada V7", output.getvalue(), contents.sha)
        st.success("✅ Sincronizado con GitHub")
    except:
        repo.create_file("malla_historica.xlsx", "Archivo Inicial", output.getvalue())

# --- 3. AUDITORÍA VISUAL ---
def auditar_malla_visual(df):
    st.divider()
    st.subheader("🛡️ Auditoría Operativa")
    
    alertas_salud = []
    for g in df['Grupo'].unique():
        g_data = df[df['Grupo'] == g].sort_values('Fecha_Raw')
        for i in range(1, len(g_data)):
            ayer, hoy = g_data.iloc[i-1]['Turno'], g_data.iloc[i]['Turno']
            if ayer == "T3" and hoy in ["T1", "T2"]:
                alertas_salud.append({"Fecha": g_data.iloc[i]['Fecha_Col'], "Grupo": g, "Fallo": f"{ayer} → {hoy}"})

    cobertura = df.groupby(['Fecha_Col', 'Turno'], observed=False).size().unstack(fill_value=0)
    dias_sin_cob = [f for f in cobertura.index if any(cobertura.loc[f, t] == 0 for t in ["T1", "T2", "T3"])]

    m1, m2, m3 = st.columns(3)
    m1.metric("Saltos de Salud", len(alertas_salud), delta_color="inverse")
    m2.metric("Días sin Cobertura", len(dias_sin_cob), delta_color="inverse")
    m3.metric("Equidad T3", f"{df[df['Turno']=='T3'].groupby('Grupo').size().std():.2f} σ")

    if alertas_salud or dias_sin_cob:
        with st.expander("🔍 Ver Inconsistencias"):
            if alertas_salud: st.table(pd.DataFrame(alertas_salud))
            if dias_sin_cob: st.error(f"Falta T1, T2 o T3 en: {', '.join(dias_sin_cob)}")

# --- 4. PANTALLA PRINCIPAL ---
def pantalla_programador():
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    with st.container(border=True):
        st.subheader("⚙️ Configuración de Staffing y Descansos")
        c_desc, c_staff = st.columns([2, 1])
        with c_desc:
            cd1, cd2 = st.columns(2)
            d_g1 = cd1.selectbox("Descanso G1", dias_semana, index=5)
            d_g2 = cd2.selectbox("Descanso G2", dias_semana, index=5)
            d_g3 = cd1.selectbox("Descanso G3", dias_semana, index=6)
            d_g4 = cd2.selectbox("Descanso G4", dias_semana, index=6)
            map_idx = {"Grupo 1": dias_semana.index(d_g1), "Grupo 2": dias_semana.index(d_g2), "Grupo 3": dias_semana.index(d_g3), "Grupo 4": dias_semana.index(d_g4)}
        with c_staff:
            rm = st.number_input("Masters", 1, 10, 3)
            rta = st.number_input("Téc A", 1, 20, 7)
            rtb = st.number_input("Téc B", 1, 20, 2)

    f_ini = st.date_input("Inicio", datetime.now())
    f_fin = st.date_input("Fin", datetime.now() + timedelta(days=28))

    if st.button("🚀 Generar Malla con Compensación Inmediata"):
        repo = conectar_github()
        estado = obtener_estado_inicial(repo)
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        
        deudas = {g: estado[g]["d"] for g in grupos_n}
        sem_deuda = {g: estado[g]["sem_deuda"] for g in grupos_n}
        
        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha); n_sem = fecha_dt.isocalendar()[1]
            dia_idx = fecha_dt.weekday(); col_name = fecha_dt.strftime('%a %d/%m')
            
            turnos_hoy = {}
            quieren_fijo = [g for g, d_idx in map_idx.items() if d_idx == dia_idx]
            
            # Priorizar compensatorio de semana pasada
            for g in grupos_n:
                if deudas[g] > 0 and n_sem > sem_deuda[g] and g not in quieren_fijo:
                    if "COMP" not in turnos_hoy.values():
                        turnos_hoy[g] = "COMP"; deudas[g] -= 1; sem_deuda[g] = 0; break

            activos = [g for g in grupos_n if g not in turnos_hoy and g not in quieren_fijo]
            while len(activos) < 3 and quieren_fijo:
                sacrificado = quieren_fijo.pop(0); deudas[sacrificado] += 1
                sem_deuda[sacrificado] = n_sem; activos.append(sacrificado)
            
            for g in quieren_fijo: turnos_hoy[g] = "DESC"
            t_op = ["T1", "T2", "T3"]; random.shuffle(t_op)
            for g in activos: turnos_hoy[g] = t_op.pop(0) if t_op else "T1"

            for g in grupos_n:
                resultados.append({"Grupo": g, "Fecha_Col": col_name, "Turno": turnos_hoy[g], "Fecha_Raw": fecha_dt, "Deuda_Compensatorio": deudas[g], "Semana_Deuda": sem_deuda[g], "M_Req": rm, "TA_Req": rta, "TB_Req": rtb})

        st.session_state.malla_generada = pd.DataFrame(resultados)
        st.rerun()

    if st.session_state.get('malla_generada') is not None:
        df_v = st.session_state.malla_generada.copy()
        matriz = df_v.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_v["Fecha_Col"].unique())
        
        st.subheader("✍️ Editor Maestro (Colores)")
        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"]) for c in matriz.columns}
        
        # EL FIX: .style.map en lugar de .applymap
        matriz_editada = st.data_editor(matriz.style.pipe(aplicar_estilos_malla), column_config=config_col, use_container_width=True)
        
        if st.button("💾 Guardar en GitHub"):
            df_man = matriz_editada.reset_index().melt(id_vars="Grupo", var_name="Fecha_Col", value_name="Turno")
            df_final = df_v.drop(columns=['Turno']).merge(df_man, on=['Grupo', 'Fecha_Col'])
            guardar_malla_github(df_final)
            st.session_state.malla_generada = df_final
            st.rerun()

        auditar_malla_visual(df_v)
