import streamlit as st
import pandas as pd
import io
import holidays
import random
from datetime import datetime, timedelta
from github import Github

# --- 1. CONFIGURACIÓN DE ESTILOS (COLORES CORREGIDOS Y LEGIBLES) ---
def aplicar_estilos_malla(styler, errores_coords):
    """
    Aplica colores de fondo y asegura que el texto sea blanco para máxima legibilidad.
    """
    def aplicar_celda(val, row_name, col_name):
        # Mapeo de colores de fondo
        colores_bg = {
            "T1": "#1f77b4",   # Azul
            "T2": "#2ca02c",   # Verde
            "T3": "#4d4d4d",   # Gris oscuro
            "DESC": "#d62728", # Rojo
            "COMP": "#ff7f0e"  # Naranja
        }
        
        bg = colores_bg.get(val, "transparent")
        color_texto = "white" if val in colores_bg else "black"
        
        estilo = f"background-color: {bg}; color: {color_texto}; font-weight: bold; text-align: center;"
        
        # RESALTADO DE ERRORES: Borde amarillo neón si la celda tiene novedad
        if (row_name, col_name) in errores_coords:
            estilo += "border: 3px solid #FFFF00 !important; box-shadow: inset 0 0 10px #FFFF00;"
        
        return estilo

    return styler.apply(lambda df: pd.DataFrame(
        [[aplicar_celda(df.iloc[r, c], df.index[r], df.columns[c]) 
          for c in range(len(df.columns))] 
         for r in range(len(df.index))],
        index=df.index, columns=df.columns), axis=None)

# --- 2. AUDITORÍA ---
def detectar_novedades(df):
    novedades = []
    if df.empty: return novedades
    # Errores de Salud (T3 seguido de T1 o T2)
    for g in df['Grupo'].unique():
        g_data = df[df['Grupo'] == g].sort_values('Fecha_Raw')
        for i in range(1, len(g_data)):
            ayer, hoy = g_data.iloc[i-1]['Turno'], g_data.iloc[i]['Turno']
            if ayer == "T3" and hoy in ["T1", "T2"]:
                novedades.append({"Grupo": g, "Fecha_Col": g_data.iloc[i]['Fecha_Col'], "Motivo": f"Salto {ayer}->{hoy}"})
    
    # Cobertura
    cob = df.groupby(['Fecha_Col', 'Turno'], observed=False).size().unstack(fill_value=0)
    for fecha in cob.index:
        for t in ["T1", "T2", "T3"]:
            if t not in cob.columns or cob.loc[fecha, t] == 0:
                novedades.append({"Grupo": "SISTEMA", "Fecha_Col": fecha, "Motivo": f"Falta {t}"})
    return novedades

# --- 3. PERSISTENCIA ---
def conectar_github():
    if "GITHUB_TOKEN" not in st.secrets: return None
    try: return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
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
                estado[g] = {"u": u['Turno'], "d": int(u.get('Deuda_Compensatorio', 0)), "sem_d": int(u.get('Semana_Deuda', 0))}
            else:
                estado[g] = {"u": "DESC", "d": 0, "sem_d": 0}
        return estado
    except:
        return {g: {"u": "DESC", "d": 0, "sem_d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

# --- 4. PROGRAMADOR ---
def pantalla_programador():
    st.title("🛡️ Programador Maestro MovilGo")
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

    with st.container(border=True):
        st.subheader("⚙️ Staffing y Descansos")
        c_desc, c_staff = st.columns([2, 1])
        with c_desc:
            cd1, cd2 = st.columns(2)
            d_g1 = cd1.selectbox("G1", dias_semana, index=5)
            d_g2 = cd2.selectbox("G2", dias_semana, index=5)
            d_g3 = cd1.selectbox("G3", dias_semana, index=6)
            d_g4 = cd2.selectbox("G4", dias_semana, index=6)
            map_idx = {"Grupo 1": dias_semana.index(d_g1), "Grupo 2": dias_semana.index(d_g2), "Grupo 3": dias_semana.index(d_g3), "Grupo 4": dias_semana.index(d_g4)}
        with c_staff:
            rm = st.number_input("Masters", 1, 10, 3)
            rta = st.number_input("Téc A", 1, 20, 7)
            rtb = st.number_input("Téc B", 1, 20, 2)

    f_ini = st.date_input("Inicio", datetime.now())
    f_fin = st.date_input("Fin", datetime.now() + timedelta(days=28))

    if st.button("🚀 Generar Malla con Cobertura Garantizada"):
        repo = conectar_github()
        estado = obtener_estado_inicial(repo)
        lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
        resultados = []
        deudas = {g: estado[g]["d"] for g in grupos_n}
        sem_deuda = {g: estado[g]["sem_d"] for g in grupos_n}
        
        for fecha in lista_fechas:
            fecha_dt = pd.to_datetime(fecha); n_sem = fecha_dt.isocalendar()[1]
            dia_idx = fecha_dt.weekday(); col_name = fecha_dt.strftime('%a %d/%m')
            turnos_hoy = {}
            quieren_fijo = [g for g, d_idx in map_idx.items() if d_idx == dia_idx]
            
            # Compensatorio
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
        df_v = st.session_state.malla_generada
        novedades = detectar_novedades(df_v)
        coords_error = [(n['Grupo'], n['Fecha_Col']) for n in novedades]

        st.subheader("🚩 Panel de Corrección")
        focus = st.toggle("Ver solo días con errores") if novedades else False
        
        matriz = df_v.pivot(index="Grupo", columns="Fecha_Col", values="Turno").reindex(columns=df_v["Fecha_Col"].unique())
        if focus and novedades:
            matriz = matriz[[n['Fecha_Col'] for n in novedades]]

        config_col = {c: st.column_config.SelectboxColumn(options=["T1", "T2", "T3", "DESC", "COMP"]) for c in matriz.columns}
        st.data_editor(matriz.style.pipe(aplicar_estilos_malla, errores_coords=coords_error), column_config=config_col, use_container_width=True)
