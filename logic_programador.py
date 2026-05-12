import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# CONFIGURACIÓN Y CONSTANTES
# =========================================================
st.set_page_config(page_title="MovilGo Optimizer Enterprise", layout="wide")

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
INICIALES = {"Lunes": "L", "Martes": "M", "Miércoles": "X", "Jueves": "J", "Viernes": "V", "Sábado": "S", "Domingo": "D"}
festivos_co = holidays.Colombia()

# Estructuras de Personal
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Personal {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}

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
        st.warning("⚠️ GitHub no conectado.")
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
                return ['background-color: #FDF2E9; border-bottom: 2px solid #E67E22;' for _ in col]
        except: pass
        return ['' for _ in col]

    return df_pivot.style.map(apply_styles).apply(highlight_special_days, axis=0)

# =========================================================
# AUDITORÍA Y MÉTRICAS
# =========================================================
def ejecutar_auditoria(df, tipo, descansos_config):
    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    
    # Validar si hay duplicidad de descansos en la configuración (exclusión mutua)
    dias_seleccionados = list(descansos_config.values())
    for d in DIAS_ES:
        if dias_seleccionados.count(d) > 1:
            grupos_conflicto = [g for g, die in descansos_config.items() if die == d]
            errores.append(f"⚠️ Conflicto: Los grupos {grupos_conflicto} tienen el mismo día de descanso ({d}).")

    if tipo == "Técnicos":
        cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
        for f, c in cobertura.items():
            if c < 3: errores.append(f"❌ Cobertura insuficiente {f.date()} ({c}/3)")
    
    return errores, (cobertura if tipo == "Técnicos" else None)

# =========================================================
# LÓGICA DE GENERACIÓN - TÉCNICOS
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos):
    carga, comp, sacr = {g:0 for g in GRUPOS_TEC}, {g:0 for g in GRUPOS_TEC}, {g:0 for g in GRUPOS_TEC}
    u_turno, c_bloque = {g: "DESCANSO" for g in GRUPOS_TEC}, {g: 0 for g in GRUPOS_TEC}
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday()
        dia_nombre = DIAS_ES[dia_idx]
        desc_dia = [g for g in GRUPOS_TEC if descansos.get(g) == dia_nombre]
        activos = [g for g in GRUPOS_TEC if g not in desc_dia]
        
        # REGLA: Si hay más de un grupo descansando o faltan activos, forzar trabajo
        while len(activos) < 3:
            mov = sorted(desc_dia, key=lambda g:(sacr[g], carga[g]))[0]
            desc_dia.remove(mov); activos.append(mov); sacr[mov]+=1; comp[mov]+=1

        asignados = {g: "DESCANSO" for g in desc_dia}
        for g in desc_dia: u_turno[g], c_bloque[g] = "DESCANSO", 0

        # Bloques y Turnos base
        for t in ["T3", "T2", "T1"]:
            cand = [g for g in activos if u_turno[g] == t and c_bloque[g] < 4]
            for g in cand:
                if g in activos: asignados[g], carga[g], c_bloque[g] = t, carga[g]+1, c_bloque[g]+1; activos.remove(g)

        for t in ["T3", "T2", "T1"]:
            if t not in asignados.values():
                pos = [g for g in activos if not (t in ["T1", "T2"] and u_turno[g] == "T3")]
                if pos:
                    sel = sorted(pos, key=lambda x: carga[x])[0]
                    asignados[sel], carga[sel], u_turno[sel], c_bloque[sel] = t, carga[sel]+1, t, 1; activos.remove(sel)

        # Apoyos y Compensados (L-V)
        for g in activos[:]:
            if comp[g] > 0 and dia_idx < 5:
                asignados[g] = "COMPENSADO"; comp[g] -= 1; u_turno[g] = "DESCANSO"
            else:
                asignados[g] = "T1 APOYO" if u_turno[g] != "T3" else "DESCANSO"
            c_bloque[g] = 0; activos.remove(g)
        
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

def generar_malla_abordaje(inicio, fin, desc_grupos, ciclo):
    filas = []
    todos = [p for sub in PERSONAL_ABO.values() for p in sub]
    for fecha in pd.date_range(inicio, fin):
        dia_idx = fecha.weekday()
        desc = [p for g in GRUPOS_ABO if desc_grupos.get(g) == DIAS_ES[dia_idx] for p in PERSONAL_ABO[g]]
        act = [p for p in todos if p not in desc]
        while len(act) < 21:
            if desc: mov = desc.pop(0); act.append(mov)
            else: break
        asig = {p: "DESCANSO" for p in desc}
        seed = (fecha - pd.to_datetime(inicio)).days if ciclo == "Diario" else (fecha.day-1)//15 + (fecha.month*10) if ciclo == "Quincenal" else fecha.month + (fecha.year*12)
        act_ord = sorted(act, key=lambda p: (hash(p) + seed) % 100)
        for _ in range(min(10, len(act_ord))): asig[act_ord.pop(0)] = "T1"
        for _ in range(min(10, len(act_ord))): asig[act_ord.pop(0)] = "T2"
        if act_ord: asig[act_ord.pop(0)] = "RELEVO"
        for p in act_ord: asig[p] = "DISPONIBLE"
        for p in todos: filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asig.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# INTERFAZ
# =========================================================
def pantalla_programador():
    st.sidebar.title("MovilGo Pro Enterprise")
    tipo = st.sidebar.radio("Personal", ["Técnicos", "Abordaje"])
    
    st.header(f"📅 Gestión de Malla: {tipo}")
    c1, c2 = st.columns(2)
    inicio, fin = c1.date_input("Desde", date.today()), c2.date_input("Hasta", date.today() + timedelta(days=30))

    descansos, ciclo = {}, "Diario"
    if tipo == "Técnicos":
        cols = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC): 
            descansos[g] = cols[i].selectbox(f"Descanso {g}", DIAS_ES, index=i)
    else:
        c_rot, c_des = st.columns([1,3])
        ciclo = c_rot.selectbox("Ciclo Rotación", ["Diario", "Quincenal", "Mensual"])
        cols_a = c_des.columns(5)
        for i, g in enumerate(GRUPOS_ABO): 
            descansos[g] = cols_a[i].selectbox(g, DIAS_ES, index=i)

    if st.button(f"🚀 Generar Malla {tipo}"):
        df = generar_malla_tecnicos(inicio, fin, descansos) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, descansos, ciclo)
        st.session_state[f"malla_{tipo}"] = df
        st.session_state[f"desc_cfg_{tipo}"] = descansos

    key = f"malla_{tipo}"
    if key in st.session_state:
        df_actual = st.session_state[key].copy()
        df_actual = df_actual.sort_values(by=["Fecha", "Sujeto"])
        df_actual["Label"] = df_actual["Fecha"].apply(lambda x: f"{INICIALES[DIAS_ES[x.weekday()]]} - {x.strftime('%Y-%m-%d')}")
        
        pivot = df_actual.pivot(index="Sujeto", columns="Label", values="Turno")
        sorted_cols = sorted(pivot.columns, key=lambda x: x.split(" - ")[1])
        pivot = pivot[sorted_cols]

        st.subheader("📝 Editor de Malla")
        config_cols = {str(c): st.column_config.SelectboxColumn(options=OPCIONES_TURNOS, width="small") for c in pivot.columns}
        df_editado = st.data_editor(style_malla(pivot), use_container_width=True, column_config=config_cols)

        if st.button("💾 Guardar y Auditar"):
            df_final = df_editado.reset_index().melt(id_vars="Sujeto", var_name="Label", value_name="Turno")
            df_final["Fecha"] = pd.to_datetime(df_final["Label"].apply(lambda x: x.split(" - ")[1]))
            st.session_state[key] = df_final
            guardar_github(df_final, f"malla_{tipo.lower()}.xlsx")
            st.success("✅ Guardado.")

        st.divider()
        errores, cobertura = ejecutar_auditoria(st.session_state[key], tipo, st.session_state.get(f"desc_cfg_{tipo}", {}))
        col_m1, col_m2 = st.columns([1, 2])
        with col_m1:
            st.metric("Alertas Activas", len(errores))
            if errores:
                for e in errores: st.error(e)
            else: st.success("Malla sin conflictos de descanso ni cobertura.")
        with col_m2:
            if cobertura is not None:
                st.subheader("📈 Cobertura")
                st.line_chart(cobertura)

if __name__ == "__main__":
    pantalla_programador()
    pantalla_programador()
