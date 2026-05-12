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
festivos_co = holidays.Colombia()

# Estructuras de Personal
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Personal {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}

# Opciones para el menú desplegable en el editor
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
        st.warning("⚠️ No se pudo conectar a GitHub (revisar Token)")
        return
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    data = buffer.getvalue()
    try:
        file = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, f"Update {datetime.now()}", data, file.sha)
    except:
        repo.create_file(nombre_archivo, "Create", data)

# Diccionario de colores (CSS HEX)
COLORES_MAP = {
    "T1": "#D6EAF8",
    "T2": "#D5F5E3",
    "T3": "#FADBD8",
    "RELEVO": "#E8DAEF",
    "DISPONIBLE": "#EAEDED",
    "T1 APOYO": "#EBF5FB",
    "DESCANSO": "#2C3E50",
    "COMPENSADO": "#FDEBD0"
}

def color_cells_df(val):
    bg_color = COLORES_MAP.get(val, "")
    text_color = "white" if val == "DESCANSO" else "black"
    if bg_color:
        return f'background-color: {bg_color}; color: {text_color}'
    return ''

# =========================================================
# AUDITORÍA DE SEGURIDAD Y COBERTURA
# =========================================================
def ejecutar_auditoria(df, tipo):
    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    
    if tipo == "Técnicos":
        cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
        for f, c in cobertura.items():
            if c < 3: errores.append(f"❌ Cobertura insuficiente el {f.date()} ({c}/3)")
        
        for g in GRUPOS_TEC:
            gdf = df[df["Sujeto"] == g].sort_values("Fecha")
            prev = None
            for _, r in gdf.iterrows():
                if prev == "T3" and r["Turno"] in ["T1", "T2", "T1 APOYO"]:
                    errores.append(f"🚨 {g}: Salto ilegal T3 ➔ {r['Turno']} el {r['Fecha'].date()}")
                prev = r["Turno"]
    else:
        t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
        t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
        for f in t1.index:
            if t1.get(f,0) < 10 or t2.get(f,0) < 10:
                errores.append(f"⚠️ Personal insuficiente {f.date()}")
        cobertura = t1 + t2
    return errores, cobertura

# =========================================================
# LÓGICAS DE GENERACIÓN
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos):
    carga, comp, sacr = {g:0 for g in GRUPOS_TEC}, {g:0 for g in GRUPOS_TEC}, {g:0 for g in GRUPOS_TEC}
    u_turno, c_bloque = {g: "DESCANSO" for g in GRUPOS_TEC}, {g: 0 for g in GRUPOS_TEC}
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia = DIAS_ES[fecha.weekday()]
        desc_dia = [g for g in GRUPOS_TEC if descansos.get(g) == dia]
        activos = [g for g in GRUPOS_TEC if g not in desc_dia]
        while len(activos) < 3:
            mov = sorted(desc_dia, key=lambda g:(sacr[g], carga[g]))[0]
            desc_dia.remove(mov); activos.append(mov); sacr[mov]+=1; comp[mov]+=1
        asignados = {g: "DESCANSO" for g in desc_dia}
        for g in desc_dia: u_turno[g], c_bloque[g] = "DESCANSO", 0
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
        for g in activos:
            if comp[g] > 0: asignados[g], comp[g], u_turno[g] = "COMPENSADO", comp[g]-1, "DESCANSO"
            else: asignados[g] = "T1 APOYO" if u_turno[g] != "T3" else "DESCANSO"
            c_bloque[g] = 0
        for g in GRUPOS_TEC: filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

def generar_malla_abordaje(inicio, fin, desc_grupos, ciclo):
    filas = []
    todos = [p for sub in PERSONAL_ABO.values() for p in sub]
    for fecha in pd.date_range(inicio, fin):
        dia = DIAS_ES[fecha.weekday()]
        desc = [p for g in GRUPOS_ABO if desc_grupos.get(g) == dia for p in PERSONAL_ABO[g]]
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
# INTERFAZ PRINCIPAL
# =========================================================
def pantalla_programador():
    st.sidebar.title("MovilGo Enterprise")
    tipo = st.sidebar.radio("Personal", ["Técnicos", "Abordaje"])
    
    st.header(f"📅 Gestión de Malla: {tipo}")
    
    # Rango de fechas
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Fecha Inicio", date.today())
    fin = c2.date_input("Fecha Fin", date.today() + timedelta(days=30))

    # Parámetros de descanso y rotación
    descansos, ciclo = {}, "Diario"
    if tipo == "Técnicos":
        st.info("💡 Lógica activa: Bloques de 4 días y prohibición de salto T3 ➔ T1/T2.")
        cols = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC):
            descansos[g] = cols[i].selectbox(f"Descanso {g}", DIAS_ES, index=i)
    else:
        st.subheader("Configuración Grupos Abordaje")
        c_rot, c_des = st.columns([1,3])
        ciclo = c_rot.selectbox("Ciclo Rotación", ["Diario", "Quincenal", "Mensual"])
        cols_a = c_des.columns(5)
        for i, g in enumerate(GRUPOS_ABO):
            descansos[g] = cols_a[i].selectbox(g, DIAS_ES, index=i)

    # Botón Generar
    if st.button(f"🚀 Generar Malla {tipo}"):
        df = generar_malla_tecnicos(inicio, fin, descansos) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, descansos, ciclo)
        st.session_state[f"malla_{tipo}"] = df
        st.success("Malla generada. Revise el editor abajo.")

    # Módulo de Edición
    key = f"malla_{tipo}"
    if key in st.session_state:
        df_actual = st.session_state[key]
        pivot = df_actual.pivot(index="Sujeto", columns="Fecha", values="Turno").sort_index(axis=1)
        
        st.subheader("📝 Editor con Menú Desplegable y Colores")
        st.markdown("👉 *Doble clic para editar. Selecciona el turno de la lista.*")

        # Corrección técnica para Pandas 2.1+ y Streamlit
        # Usamos .map() en lugar de .applymap() para los colores
        df_estilizado = pivot.style.map(color_cells_df)

        # Configuración de columnas para Dropdown dinámico
        config_cols = {
            col: st.column_config.SelectboxColumn(
                str(col.date()) if hasattr(col, 'date') else str(col),
                options=OPCIONES_TURNOS,
                width="small"
            ) for col in pivot.columns
        }

        # Renderizado del EDITOR
        df_editado = st.data_editor(
            df_estilizado, 
            use_container_width=True, 
            key=f"editor_{tipo}",
            column_config=config_cols
        )

        # Botón Guardar
        if st.button("💾 Guardar Cambios"):
            # Revertir pivot a formato largo
            df_final = df_editado.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
            st.session_state[key] = df_final
            guardar_github(df_final, f"malla_{tipo.lower()}.xlsx")
            st.toast("✅ Sincronizado con GitHub")

        # Sección de Auditoría
        err, cob = ejecutar_auditoria(st.session_state[key], tipo)
        col_err, col_graf = st.columns([1, 1])
        with col_err:
            st.subheader("🚨 Auditoría de Salud")
            if err: 
                for e in err[:15]: st.error(e)
            else: st.success("✅ Malla sin infracciones detectadas.")
        with col_graf:
            st.subheader("📈 Cobertura Diaria")
            st.line_chart(cob)

if __name__ == "__main__":
    pantalla_programador()
