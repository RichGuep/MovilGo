import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# CONFIGURACIÓN Y CONSTANTES
# =========================================================
st.set_page_config(page_title="MovilGo Pro Enterprise v3.5", layout="wide")

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
OPCIONES_TURNOS = ["T1", "T2", "T3", "RELEVO", "DISPONIBLE", "T1 APOYO", "DESCANSO", "COMPENSADO"]

# =========================================================
# CONECTIVIDAD Y ESTILOS
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def guardar_github(df, nombre_archivo):
    repo = conectar_github()
    if not repo:
        st.warning("⚠️ GitHub no configurado.")
        return
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    try:
        file = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, f"Update {datetime.now()}", buffer.getvalue(), file.sha)
    except:
        repo.create_file(nombre_archivo, "Create", buffer.getvalue())

COLORES_MAP = {
    "T1": "#D6EAF8", "T2": "#D5F5E3", "T3": "#FADBD8",
    "RELEVO": "#E8DAEF", "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB", "DESCANSO": "#2C3E50", "COMPENSADO": "#FDEBD0"
}

def style_malla(df_pivot):
    def apply_styles(val):
        bg = COLORES_MAP.get(val, "")
        txt = "white" if val == "DESCANSO" else "black"
        return f'background-color: {bg}; color: {txt}' if bg else ''

    def highlight_special_days(col):
        try:
            fecha_str = col.name.split(" - ")[1]
            fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            if fecha_obj.weekday() >= 5 or fecha_obj in festivos_co:
                return ['background-color: #FDF2E9; border-bottom: 3px solid #E67E22;' for _ in col]
        except: pass
        return ['' for _ in col]

    return df_pivot.style.map(apply_styles).apply(highlight_special_days, axis=0)

# =========================================================
# LÓGICA DE AUDITORÍA
# =========================================================
def ejecutar_auditoria(df):
    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    
    # 1. Cobertura
    cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
    for f, c in cobertura.items():
        if c < 3: errores.append(f"❌ Cobertura insuficiente el {f.date()} ({c}/3)")
    
    # 2. Saltos y Compensados
    for g in GRUPOS_TEC:
        gdf = df[df["Sujeto"] == g].sort_values("Fecha")
        prev = None
        for _, r in gdf.iterrows():
            if prev == "T3" and r["Turno"] in ["T1", "T2"]:
                errores.append(f"🚨 {g}: Salto ilegal T3 ➔ {r['Turno']} el {r['Fecha'].date()}")
            if r["Turno"] == "COMPENSADO" and r["Fecha"].weekday() >= 5:
                errores.append(f"⚠️ {g}: Compensado en Fin de Semana ({r['Fecha'].date()})")
            prev = r["Turno"]
            
    return errores, cobertura

# =========================================================
# LÓGICA DE GENERACIÓN (TECNICOS)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_compensado = {g: 0 for g in GRUPOS_TEC}
    grupos_por_dia = {dia: [g for g, d in descansos_ley.items() if d == dia] for dia in ["Sábado", "Domingo"]}
    
    u_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    c_bloque = {g: 0 for g in GRUPOS_TEC}

    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday()
        dia_nombre = DIAS_ES[dia_idx]
        asignaciones_hoy = {}
        
        # 1. GESTIÓN DE DESCANSOS DE LEY Y VICEVERSA (SÁB/DOM)
        if dia_nombre in ["Sábado", "Domingo"]:
            g_en_conflicto = grupos_por_dia[dia_nombre]
            if len(g_en_conflicto) > 1:
                # Alternancia por semana del año
                semana_par = (fecha.isocalendar()[1] % 2 == 0)
                descansa_hoy = g_en_conflicto[0] if semana_par else g_en_conflicto[1]
                trabaja_hoy = g_en_conflicto[1] if semana_par else g_en_conflicto[0]
                
                asignaciones_hoy[descansa_hoy] = "DESCANSO"
                deudas_compensado[trabaja_hoy] += 1
            else:
                for g in g_en_conflicto: asignaciones_hoy[g] = "DESCANSO"
        
        # 2. ASIGNAR COMPENSADOS (L-V)
        activos = [g for g in GRUPOS_TEC if g not in asignaciones_hoy]
        if 0 <= dia_idx <= 4:
            for g in activos[:]:
                if deudas_compensado[g] > 0:
                    asignaciones_hoy[g] = "COMPENSADO"
                    deudas_compensado[g] -= 1
                    activos.remove(g)

        # 3. TURNOS BASE (T3, T2, T1)
        for t in ["T3", "T2", "T1"]:
            # Continuidad de bloque
            for g in activos[:]:
                if u_turno[g] == t and c_bloque[g] < 4:
                    asignaciones_hoy[g] = t
                    c_bloque[g] += 1
                    activos.remove(g)
            # Nuevas asignaciones
            if t not in asignaciones_hoy.values() and activos:
                cands = [g for g in activos if not (t in ["T1", "T2"] and u_turno[g] == "T3")]
                if cands:
                    sel = cands[0]
                    asignaciones_hoy[sel] = t
                    u_turno[sel] = t
                    c_bloque[sel] = 1
                    activos.remove(sel)

        # 4. LIMPIEZA DE ACTIVOS
        for g in activos:
            asignaciones_hoy[g] = "DESCANSO" if u_turno[g] == "T3" else "T1 APOYO"
            c_bloque[g] = 0

        for g in GRUPOS_TEC:
            u_turno[g] = asignaciones_hoy[g]
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignaciones_hoy[g]})

    return pd.DataFrame(filas)

# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
def pantalla_programador():
    st.sidebar.title("🛠️ MovilGo Pro Enterprise")
    st.header("📅 Planificación de Malla: Técnicos")
    
    # Filtros de fecha
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Fecha Inicio", date(2026, 7, 1))
    fin = c2.date_input("Fecha Fin", date(2026, 12, 31))

    # Configuración de Descansos
    st.subheader("⚙️ Configuración de Descansos de Ley")
    cols_d = st.columns(4)
    desc_cfg = {}
    for i, g in enumerate(GRUPOS_TEC):
        # Default G1/G3 Sáb, G2/G4 Dom
        d_idx = 5 if i % 2 == 0 else 6
        desc_cfg[g] = cols_d[i].selectbox(f"Ley {g}", DIAS_ES, index=d_idx)

    if st.button("🚀 Generar Malla Optimizada"):
        df = generar_malla_tecnicos(inicio, fin, desc_cfg)
        st.session_state["malla_main"] = df
        st.session_state["config_ley"] = desc_cfg

    if "malla_main" in st.session_state:
        # Preparación para el Editor
        df_edit = st.session_state["malla_main"].copy()
        df_edit["Label"] = df_edit["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} - {x.strftime('%Y-%m-%d')}")
        
        pivot = df_edit.pivot(index="Sujeto", columns="Label", values="Turno")
        sorted_cols = sorted(pivot.columns, key=lambda x: x.split(" - ")[1])
        pivot = pivot[sorted_cols]

        st.subheader("📝 Editor de Turnos (Dropdown + Colores)")
        st.caption("Los bordes naranjas indican días Sábado, Domingo o Festivos.")
        
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        
        df_final_edit = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols)

        if st.button("💾 Guardar Cambios y Ejecutar Auditoría"):
            # Procesar guardado
            df_save = df_final_edit.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
            df_save["Fecha"] = pd.to_datetime(df_save["Label"].apply(lambda x: x.split(" - ")[1]))
            st.session_state["malla_main"] = df_save
            guardar_github(df_save, "malla_tecnicos_v3.xlsx")
            st.toast("Guardado exitoso")

        # PANEL DE MÉTRICAS Y ALERTAS
        st.divider()
        st.subheader("📊 Auditoría y Métricas de Cobertura")
        
        errs, cob = ejecutar_auditoria(st.session_state["malla_main"])
        
        m1, m2 = st.columns([1, 2])
        with m1:
            st.metric("Alertas Activas", len(errs), delta_color="inverse")
            with st.container(height=300):
                if errs:
                    for e in errs: st.error(e)
                else:
                    st.success("✅ Malla sin conflictos detectados.")
        
        with m2:
            st.line_chart(cob)
            st.caption("Promedio de técnicos activos por día (Objetivo: 3)")

if __name__ == "__main__":
    pantalla_programador()
