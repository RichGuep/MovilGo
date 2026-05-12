import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# CONFIGURACIÓN Y CONSTANTES
# =========================================================
st.set_page_config(page_title="MovilGo Optimizer Enterprise v4.0", layout="wide")

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
# LÓGICA DE GENERACIÓN TÉCNICOS (REGLA DE EXCLUSIÓN MUTUA)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos_ley):
    filas = []
    deudas_compensado = {g: 0 for g in GRUPOS_TEC}
    u_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    c_bloque = {g: 0 for g in GRUPOS_TEC}

    # Pre-calcular grupos que comparten el mismo día de descanso
    conflictos = {dia: [g for g, d in descansos_ley.items() if d == dia] for dia in DIAS_ES}

    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday()
        dia_nombre = DIAS_ES[dia_idx]
        semana_num = fecha.isocalendar()[1]
        asignaciones_hoy = {}
        
        # 1. DETERMINAR QUIÉN DESCANSA (EXCLUSIÓN MUTUA)
        grupos_del_dia = conflictos[dia_nombre]
        
        if len(grupos_del_dia) > 1:
            # Alternancia: En semana par descansa el primero, en impar el segundo
            # Si hay más de 2, rotan por módulo
            idx_descansa = semana_num % len(grupos_del_dia)
            descansa_real = grupos_del_dia[idx_descansa]
            
            asignaciones_hoy[descansa_real] = "DESCANSO"
            # Los otros grupos del mismo día que NO descansaron ganan un compensado
            for g_trabaja in grupos_del_dia:
                if g_trabaja != descansa_real:
                    deudas_compensado[g_trabaja] += 1
        elif len(grupos_del_dia) == 1:
            asignaciones_hoy[grupos_del_dia[0]] = "DESCANSO"

        # 2. ASIGNAR COMPENSADOS (Solo Lunes a Viernes)
        activos = [g for g in GRUPOS_TEC if g not in asignaciones_hoy]
        if 0 <= dia_idx <= 4: # L-V
            # Prioridad de compensado al que tenga más deudas
            for g in sorted(activos, key=lambda x: deudas_compensado[x], reverse=True):
                if deudas_compensado[g] > 0 and g in activos:
                    asignaciones_hoy[g] = "COMPENSADO"
                    deudas_compensado[g] -= 1
                    activos.remove(g)

        # 3. ASIGNAR TURNOS BASE (T3, T2, T1) - COBERTURA 3 TÉCNICOS
        for t in ["T3", "T2", "T1"]:
            # Prioridad 1: Continuidad de bloque (Inercia)
            for g in activos[:]:
                if u_turno[g] == t and c_bloque[g] < 4:
                    asignaciones_hoy[g] = t
                    c_bloque[g] += 1
                    activos.remove(g)
            
            # Prioridad 2: Llenar el turno si quedó vacío
            if t not in asignaciones_hoy.values() and activos:
                # Evitar saltos prohibidos T3 -> T1/T2
                cands = [g for g in activos if not (t in ["T1", "T2"] and u_turno[g] == "T3")]
                if cands:
                    sel = cands[0]
                    asignaciones_hoy[sel] = t
                    u_turno[sel] = t
                    c_bloque[sel] = 1
                    activos.remove(sel)
                else: # Si no hay más opción por cobertura, asignamos al primero
                    sel = activos[0]
                    asignaciones_hoy[sel] = t
                    u_turno[sel] = t
                    c_bloque[sel] = 1
                    activos.remove(sel)

        # 4. PERSONAL RESTANTE (No pueden tener descansos extra)
        for g in activos:
            # Si sobran y vienen de T3, forzar descanso por salud, sino T1 APOYO
            asignaciones_hoy[g] = "DESCANSO" if u_turno[g] == "T3" else "T1 APOYO"
            c_bloque[g] = 0

        # Guardar historial y filas
        for g in GRUPOS_TEC:
            u_turno[g] = asignaciones_hoy[g]
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignaciones_hoy[g]})

    return pd.DataFrame(filas)

# =========================================================
# AUDITORÍA
# =========================================================
def ejecutar_auditoria(df):
    errores = []
    cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
    for f, c in cobertura.items():
        if c < 3: errores.append(f"❌ Cobertura insuficiente el {f.date()} ({c}/3)")
    return errores, cobertura

# =========================================================
# INTERFAZ
# =========================================================
def pantalla_programador():
    st.sidebar.title("MovilGo Enterprise v4.0")
    st.header("📅 Gestión de Malla: Técnicos")
    
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Desde", date(2026, 7, 1))
    fin = c2.date_input("Hasta", date(2026, 12, 31))

    st.subheader("⚙️ Parametrización de Descansos")
    st.info("Regla: Si dos grupos tienen el mismo día, el sistema los alternará para mantener 3 técnicos activos.")
    
    cols = st.columns(4)
    desc_cfg = {}
    for i, g in enumerate(GRUPOS_TEC):
        # Default sugerido para evitar colapsos
        desc_cfg[g] = cols[i].selectbox(f"Ley {g}", DIAS_ES, index=(5 if i<2 else 6))

    if st.button("🚀 Generar Malla Corregida"):
        st.session_state["malla_v4"] = generar_malla_tecnicos(inicio, fin, desc_cfg)

    if "malla_v4" in st.session_state:
        df = st.session_state["malla_v4"].copy()
        df["Label"] = df["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} - {x.strftime('%Y-%m-%d')}")
        
        pivot = df.pivot(index="Sujeto", columns="Label", values="Turno")
        sorted_cols = sorted(pivot.columns, key=lambda x: x.split(" - ")[1])
        pivot = pivot[sorted_cols]

        st.subheader("📝 Editor de Malla")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        df_editado = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols)

        if st.button("💾 Guardar Cambios"):
            df_final = df_editado.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
            df_final["Fecha"] = pd.to_datetime(df_final["Label"].apply(lambda x: x.split(" - ")[1]))
            guardar_github(df_final, "malla_tecnicos_v4.xlsx")
            st.success("Guardado en GitHub")

        # PANEL DE CONTROL
        errs, cob = ejecutar_auditoria(df)
        st.divider()
        m1, m2 = st.columns([1, 2])
        with m1:
            st.metric("Alertas", len(errs))
            for e in errs: st.error(e)
            if not errs: st.success("✅ Cobertura y Descansos OK")
        with m2:
            st.line_chart(cob)

if __name__ == "__main__":
    pantalla_programador()
    pantalla_programador()
