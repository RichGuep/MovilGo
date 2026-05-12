import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# CONFIGURACIÓN Y CONSTANTES
# =========================================================
st.set_page_config(page_title="MovilGo Optimizer Enterprise v4.5", layout="wide")

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
    if not repo: return
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
# LÓGICA DE GENERACIÓN TÉCNICOS (EXCLUSIÓN TOTAL)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_compensado = {g: 0 for g in GRUPOS_TEC}
    u_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    c_bloque = {g: 0 for g in GRUPOS_TEC}

    conflictos = {dia: [g for g, d in descansos_ley.items() if d == dia] for dia in DIAS_ES}

    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday()
        dia_nombre = DIAS_ES[dia_idx]
        semana_num = fecha.isocalendar()[1]
        asignaciones_hoy = {}
        
        # 1. GESTIÓN DE DESCANSO DE LEY (Solo 1 grupo puede descansar hoy)
        grupos_con_derecho = conflictos[dia_nombre]
        
        if len(grupos_con_derecho) > 1:
            idx_descansa = semana_num % len(grupos_con_derecho)
            descansa_real = grupos_con_derecho[idx_descansa]
            asignaciones_hoy[descansa_real] = "DESCANSO"
            for g in grupos_con_derecho:
                if g != descansa_real: deudas_compensado[g] += 1
        elif len(grupos_con_derecho) == 1:
            asignaciones_hoy[grupos_con_derecho[0]] = "DESCANSO"

        # 2. GESTIÓN DE COMPENSADOS (REGLA: Solo si NADIE está descansando por ley)
        # Y solo de lunes a viernes, máximo 1 por día
        activos = [g for g in GRUPOS_TEC if g not in asignaciones_hoy]
        
        if 0 <= dia_idx <= 4 and len(asignaciones_hoy) == 0:
            # Buscamos quién tiene más deuda para darle su compensado hoy
            posibles_comp = sorted(activos, key=lambda x: deudas_compensado[x], reverse=True)
            if deudas_compensado[posibles_comp[0]] > 0:
                sel_comp = posibles_comp[0]
                asignaciones_hoy[sel_comp] = "COMPENSADO"
                deudas_compensado[sel_comp] -= 1
                activos.remove(sel_comp)

        # 3. ASIGNAR TURNOS OPERATIVOS (T1, T2, T3)
        # Garantizamos que al menos 3 personas estén trabajando
        for t in ["T3", "T2", "T1"]:
            # Prioridad Bloque
            for g in activos[:]:
                if u_turno[g] == t and c_bloque[g] < 4:
                    asignaciones_hoy[g] = t
                    c_bloque[g] += 1
                    activos.remove(g)
                    break # Asignar solo a uno por turno
            
            # Si el turno sigue vacío
            if t not in asignaciones_hoy.values() and activos:
                cands = [g for g in activos if not (t in ["T1", "T2"] and u_turno[g] == "T3")]
                sel = cands[0] if cands else activos[0]
                asignaciones_hoy[sel] = t
                u_turno[sel] = t
                c_bloque[sel] = 1
                activos.remove(sel)

        # 4. PERSONAL SOBRANTE (T1 APOYO)
        for g in activos:
            asignaciones_hoy[g] = "DESCANSO" if u_turno[g] == "T3" else "T1 APOYO"
            c_bloque[g] = 0

        for g in GRUPOS_TEC:
            u_turno[g] = asignaciones_hoy.get(g, "T1 APOYO")
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignaciones_hoy.get(g, "T1 APOYO")})

    return pd.DataFrame(filas)

# =========================================================
# AUDITORÍA
# =========================================================
def ejecutar_auditoria(df):
    errores = []
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    
    # Validar exclusión mutua: No más de 1 persona fuera de turno operativo por día
    # Turnos operativos: T1, T2, T3, T1 APOYO
    fuera_de_turno = df[df["Turno"].isin(["DESCANSO", "COMPENSADO"])].groupby("Fecha").size()
    for f, c in fuera_de_turno.items():
        if c > 1:
            errores.append(f"🚨 Error de Exclusión: {c} grupos descansando el {f.date()}. Solo se permite 1.")
            
    cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
    return errores, cobertura

# =========================================================
# INTERFAZ
# =========================================================
def pantalla_programador():
    st.sidebar.title("MovilGo Enterprise v4.5")
    st.header("📅 Gestión de Malla: Técnicos")
    
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Desde", date(2026, 7, 1))
    fin = c2.date_input("Hasta", date(2026, 12, 31))

    st.subheader("⚙️ Parametrización de Descansos")
    cols = st.columns(4)
    desc_cfg = {}
    for i, g in enumerate(GRUPOS_TEC):
        desc_cfg[g] = cols[i].selectbox(f"Ley {g}", DIAS_ES, index=(5 if i<2 else 6))

    if st.button("🚀 Generar Malla de Alta Disponibilidad"):
        st.session_state["malla_v45"] = generar_malla_tecnicos(inicio, fin, desc_cfg)

    if "malla_v45" in st.session_state:
        df = st.session_state["malla_v45"].copy()
        df["Label"] = df["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} - {x.strftime('%Y-%m-%d')}")
        
        pivot = df.pivot(index="Sujeto", columns="Label", values="Turno")
        sorted_cols = sorted(pivot.columns, key=lambda x: x.split(" - ")[1])
        pivot = pivot[sorted_cols]

        st.subheader("📝 Editor de Malla")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        df_editado = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols)

        if st.button("💾 Guardar y Validar"):
            df_final = df_editado.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
            df_final["Fecha"] = pd.to_datetime(df_final["Label"].apply(lambda x: x.split(" - ")[1]))
            guardar_github(df_final, "malla_tecnicos_v45.xlsx")
            st.toast("Guardado en GitHub")

        errs, cob = ejecutar_auditoria(df)
        st.divider()
        m1, m2 = st.columns([1, 2])
        with m1:
            st.metric("Alertas Críticas", len(errs))
            for e in errs: st.error(e)
            if not errs: st.success("✅ Exclusión Mutua Garantizada (Solo 1 ausente por día)")
        with m2:
            st.line_chart(cob)

if __name__ == "__main__":
    pantalla_programador()
