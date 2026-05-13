import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# 1. CONFIGURACIÓN Y ESTILOS AVANZADOS (UI/UX)
# =========================================================
st.set_page_config(page_title="MovilGo Optimizer Enterprise Pro v5.0", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #F4F7F9; }
    .main-header { font-size: 30px; font-weight: 800; color: #1E3A8A; margin-bottom: 20px; text-transform: uppercase; letter-spacing: -1px; }
    .metric-container { background-color: white; padding: 20px; border-radius: 12px; border: 1px solid #E2E8F0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    [data-testid="stDataEditor"] { border: 1px solid #DEE2E6; border-radius: 12px; overflow: hidden; }
    .stButton>button { border-radius: 8px; font-weight: bold; height: 3em; transition: all 0.3s; }
    </style>
    """, unsafe_allow_html=True)

# Constantes Globales
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Abordaje {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}
OPCIONES_TURNOS = ["T1", "T2", "T3", "RELEVO", "DISPONIBLE", "T1 APOYO", "DESCANSO", "COMPENSADO"]

# Mapa de Colores Enterprise
COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#1B2631", "COMPENSADO": "#FDEBD0"
}

def style_malla(df_pivot):
    def apply_styles(val):
        bg = COLORES_MAP.get(val, "")
        txt = "white" if val == "DESCANSO" else "#17202A"
        return f'background-color: {bg}; color: {txt}; font-weight: 700; border: 0.5px solid #D5DBDB' if bg else ''
    return df_pivot.style.map(apply_styles)

# =========================================================
# 2. CONECTIVIDAD GITHUB Y EXPORTACIÓN
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def guardar_github(df, nombre_archivo):
    repo = conectar_github()
    if not repo: return
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    try:
        file = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, f"Update {datetime.now()}", buffer.getvalue(), file.sha)
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())

def generar_excel_completo(df_edit, errs, cob, equidad):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_edit.to_excel(writer, sheet_name='Malla_Final')
        equidad.to_excel(writer, sheet_name='Analisis_Equidad')
        pd.DataFrame(errs, columns=["Alertas_Auditoria"]).to_excel(writer, sheet_name='Auditoria', index=False)
        cob.reset_index().to_excel(writer, sheet_name='Cobertura_Diaria', index=False)
        for sheet in writer.sheets.values(): sheet.set_column('A:Z', 18)
    return output.getvalue()

# =========================================================
# 3. LÓGICAS DE GENERACIÓN (EQUIDAD + DEUDAS)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_comp = {g: 0 for g in GRUPOS_TEC}
    
    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday(); dia_nombre = DIAS_ES[dia_idx]; sem_num = fecha.isocalendar()[1]
        asignados = {}
        
        # 1. Descansos Legales (con rotación si hay conflicto)
        gps_hoy = [g for g, d in descansos_ley.items() if d == dia_nombre]
        if len(gps_hoy) > 1:
            idx = sem_num % len(gps_hoy)
            descansador = gps_hoy[idx]; asignados[descansador] = "DESCANSO"
            for g in gps_hoy: 
                if g != descansador: deudas_comp[g] += 1
        elif len(gps_hoy) == 1:
            asignados[gps_hoy[0]] = "DESCANSO"

        # 2. Rotación de Prioridad Semanal (Equidad de carga T3/T2)
        activos = [g for g in GRUPOS_TEC if g not in asignados]
        offset = sem_num % len(GRUPOS_TEC)
        activos_rotados = sorted(activos, key=lambda x: (GRUPOS_TEC.index(x) + offset) % len(GRUPOS_TEC))

        # 3. Pago de Deudas (Compensatorios en semana)
        if 0 <= dia_idx <= 4 and len(asignados) == 0:
            cands = sorted(activos_rotados, key=lambda x: deudas_comp[x], reverse=True)
            if deudas_comp[cands[0]] > 0:
                sel = cands[0]; asignados[sel] = "COMPENSADO"; deudas_comp[sel] -= 1; activos_rotados.remove(sel)

        # 4. Distribución Operativa Round-Robin
        turnos_op = ["T3", "T2", "T1", "T1 APOYO"]
        for g in activos_rotados:
            for t in turnos_op:
                if t not in asignados.values():
                    asignados[g] = t; break
            if g not in asignados: asignados[g] = "T1 APOYO"

        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

def generar_malla_abordaje(inicio, fin, desc_cfg, ciclo):
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_nombre = DIAS_ES[fecha.weekday()]
        gps_descansan = [g for g in GRUPOS_ABO if desc_cfg.get(g) == dia_nombre]
        
        seed = (fecha - pd.to_datetime(inicio)).days if ciclo == "Diario" else fecha.month
        gps_ord = sorted(GRUPOS_ABO, key=lambda g: (hash(g) + seed) % 100)
        disponibles = [g for g in gps_ord if g not in gps_descansan]
        
        asig_gps = {}
        for _ in range(min(2, len(disponibles))): asig_gps[disponibles.pop(0)] = "T1"
        for _ in range(min(2, len(disponibles))): asig_gps[disponibles.pop(0)] = "T2"
        gp_sobrante = disponibles[0] if disponibles else None
        
        for g in GRUPOS_ABO:
            turno_base = asig_gps.get(g, "DESCANSO")
            for i, p in enumerate(PERSONAL_ABO[g]):
                ft = turno_base
                if g == gp_sobrante: ft = "RELEVO" if i == 0 else "DISPONIBLE"
                elif g in gps_descansan: ft = "DESCANSO"
                filas.append({"Fecha": fecha, "Sujeto": p, "Turno": ft})
    return pd.DataFrame(filas)

# =========================================================
# 4. AUDITORÍA Y DASHBOARD DE COMPORTAMIENTO
# =========================================================
def ejecutar_auditoria_completa(df, tipo):
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    cob = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
    errs = [f"❌ Cobertura insuficiente {f.date()}" for f, c in cob.items() if c < (3 if tipo=="Técnicos" else 20)]
    
    # Métricas de Equidad
    equidad = df.groupby(["Sujeto", "Turno"]).size().unstack(fill_value=0)
    for c in ["DESCANSO", "COMPENSADO", "T1", "T2", "T3"]:
        if c not in equidad.columns: equidad[c] = 0
    equidad["Días_Trabajados"] = equidad.drop(columns=["DESCANSO", "COMPENSADO"], errors='ignore').sum(axis=1)
    
    return errs, cob, equidad

# =========================================================
# 5. INTERFAZ PRINCIPAL
# =========================================================
def pantalla_programador():
    st.sidebar.title("MovilGo Control Center")
    tipo = st.sidebar.radio("Sección Operativa", ["Técnicos", "Abordaje"])
    
    st.markdown(f"<div class='main-header'>📅 Planificación: {tipo}</div>", unsafe_allow_html=True)
    
    with st.container(border=True):
        c1, c2 = st.columns(2)
        inicio = c1.date_input("Fecha Inicio", date.today())
        fin = c2.date_input("Fecha Término", date.today() + timedelta(days=28))
        
        desc_cfg = {}
        lista = GRUPOS_TEC if tipo == "Técnicos" else GRUPOS_ABO
        cols = st.columns(len(lista))
        for i, g in enumerate(lista):
            desc_cfg[g] = cols[i].selectbox(f"Libra {g}", DIAS_ES, index=(5 if i<2 else 6) if tipo == "Técnicos" else i%7)
        ciclo = st.sidebar.selectbox("Ciclo Rotación", ["Diario", "Quincenal", "Mensual"]) if tipo == "Abordaje" else "Fijo"

    if st.button(f"⚡ Generar Escenario Equitativo", use_container_width=True):
        st.session_state[f"m_{tipo}"] = generar_malla_tecnicos(inicio, fin, desc_cfg) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, desc_cfg, ciclo)

    key = f"m_{tipo}"
    if key in st.session_state:
        df_view = st.session_state[key].copy()
        df_view["Label"] = df_view["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} {x.strftime('%d/%m')}")
        pivot = df_view.pivot(index="Sujeto", columns="Label", values="Turno")
        sorted_cols = sorted(pivot.columns, key=lambda x: datetime.strptime(x.split(" ")[1] + f"/{date.today().year}", '%d/%m/%Y'))
        
        st.subheader("📝 Editor Maestro de Turnos")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        df_edit = st.data_editor(style_malla(pivot[sorted_cols]), use_container_width=True, column_config=config_cols)

        # Procesamiento Post-Edición
        df_final = df_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
        map_fechas = dict(zip(df_view["Label"], df_view["Fecha"]))
        df_final["Fecha"] = df_final["Label"].map(map_fechas)
        errs, cob, equidad = ejecutar_auditoria_completa(df_final, tipo)

        st.divider()
        st.subheader("📊 Dashboard de Comportamiento y Equidad")
        m1, m2 = st.columns([1, 1])
        with m1:
            st.markdown("**Resumen de Carga por Grupo**")
            st.dataframe(equidad.style.highlight_max(axis=0, color='#FADBD8').format(precision=0), use_container_width=True)
        with m2:
            st.markdown("**Balance de Turnos Operativos**")
            st.bar_chart(equidad[["T1", "T2", "T3"]])

        # Acciones Finales
        st.divider()
        f1, f2 = st.columns(2)
        with f1:
            if st.button("💾 Sincronizar con GitHub", use_container_width=True):
                guardar_github(df_final, f"malla_{tipo.lower()}.xlsx"); st.success("Sincronizado")
        with f2:
            excel = generar_excel_completo(df_edit, errs, cob, equidad)
            st.download_button("📥 Descargar Reporte Completo con Métricas", excel, f"Reporte_{tipo}.xlsx", use_container_width=True)

        if errs:
            with st.expander("🚨 Ver Alertas de Auditoría"):
                for e in errs: st.error(e)

if __name__ == "__main__":
    pantalla_programador()
