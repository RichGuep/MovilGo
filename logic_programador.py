# logic_programador.py
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - MULTI-PERSONAL
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# =========================================================
# CONFIGURACIÓN Y CONSTANTES
# =========================================================
st.set_page_config(page_title="MovilGo Optimizer Pro", layout="wide")

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
festivos_co = holidays.Colombia()

# Config Técnicos
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]

# Config Abordaje (5 Grupos x 5 Personas = 25)
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Personal {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}

# =========================================================
# GITHUB INTEGRATION
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except:
        return None

def guardar_github(df, nombre_archivo):
    repo = conectar_github()
    if not repo:
        st.warning("⚠️ No se detectó GITHUB_TOKEN en secrets.")
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

# =========================================================
# ESTILOS VISUALES
# =========================================================
def color_cell(v):
    colores = {
        "T1":"background-color:#D6EAF8;color:#1B4F72;",
        "T2":"background-color:#D5F5E3;color:#145A32;",
        "T3":"background-color:#FADBD8;color:#7B241C;",
        "RELEVO":"background-color:#E8DAEF;color:#4A235A;font-weight:bold;",
        "DISPONIBLE":"background-color:#EAEDED;color:#7F8C8D;",
        "T1 APOYO":"background-color:#EBF5FB;",
        "T2 APOYO":"background-color:#EAF2F8;",
        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;font-weight:700;",
        "COMPENSADO":"background-color:#FDEBD0;"
    }
    return colores.get(v,"")

# =========================================================
# AUDITORÍA
# =========================================================
def auditoria(df, tipo):
    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    if tipo == "Técnicos":
        cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
        for f,c in cobertura.items():
            if c < 3: errores.append(f"❌ Cobertura insuficiente {f.date()} ({c}/3)")
    else:
        # Auditoría Abordaje (10 T1 y 10 T2)
        t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
        t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
        cobertura = t1 + t2
        for f in t1.index:
            if t1[f] < 10 or t2[f] < 10:
                errores.append(f"❌ Abordaje incompleto {f.date()}: T1({t1[f]}), T2({t2[f]})")

    return errores, cobertura

# =========================================================
# LÓGICA DE GENERACIÓN - TÉCNICOS (ORIGINAL)
# =========================================================
def generar_logica_tecnicos(inicio, fin, descansos):
    carga = {g:0 for g in GRUPOS_TEC}
    conteo = {g:{"T1":0,"T2":0,"T3":0} for g in GRUPOS_TEC}
    compensado = {g:0 for g in GRUPOS_TEC}
    sacrificio = {g:0 for g in GRUPOS_TEC}
    filas = []
    fechas = pd.date_range(inicio, fin)

    for fecha in fechas:
        dia = DIAS_ES[fecha.weekday()]
        festivo = fecha.date() in festivos_co
        asignados = {}
        descanso_dia = [g for g in GRUPOS_TEC if descansos[g]==dia]
        activos = [g for g in GRUPOS_TEC if g not in descanso_dia]

        while len(activos) < 3:
            mov = sorted(descanso_dia, key=lambda g:(sacrificio[g], carga[g]))[0]
            descanso_dia.remove(mov)
            activos.append(mov)
            sacrificio[mov]+=1
            compensado[mov]+=1

        for g in descanso_dia: asignados[g]="DESCANSO"
        for turno in ["T1","T2","T3"]:
            sel = sorted(activos, key=lambda g:(carga[g], conteo[g][turno]))[0]
            asignados[sel]=turno
            carga[sel]+=1
            conteo[sel][turno]+=1
            activos.remove(sel)
        for g in activos:
            if compensado[g]>0: asignados[g]="COMPENSADO"; compensado[g]-=1
            else: asignados[g]="T1 APOYO"
        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Día": dia, "Sujeto": g, "Turno": asignados[g], "Festivo": "SI" if festivo else "NO"})
    return pd.DataFrame(filas)

# =========================================================
# LÓGICA DE GENERACIÓN - ABORDAJE (NUEVA CON ROTACIÓN)
# =========================================================
def generar_logica_abordaje(inicio, fin, descansos_grupos, ciclo):
    filas = []
    fechas = pd.date_range(inicio, fin)
    todos = [p for sub in PERSONAL_ABO.values() for p in sub]
    carga = {p:0 for p in todos}
    sacrificio = {p:0 for p in todos}
    compensado = {p:0 for p in todos}

    for fecha in fechas:
        dia = DIAS_ES[fecha.weekday()]
        festivo = fecha.date() in festivos_co
        asignados = {}
        
        # 1. Descansos por Grupo
        descansan_hoy = []
        for g in GRUPOS_ABO:
            if descansos_grupos[g] == dia:
                descansan_hoy.extend(PERSONAL_ABO[g])
        
        activos = [p for p in todos if p not in descansan_hoy]

        # 2. Mínimo 21 (10 T1 + 10 T2 + 1 Relevo)
        while len(activos) < 21:
            mov = sorted(descansan_hoy, key=lambda p:(sacrificio[p], carga[p]))[0]
            descansan_hoy.remove(mov)
            activos.append(mov)
            sacrificio[mov]+=1
            compensado[mov]+=1

        for p in descansan_hoy: asignados[p]="DESCANSO"

        # 3. Lógica de Rotación (Estabilidad)
        if ciclo == "Diario": seed = (fecha - pd.to_datetime(inicio)).days
        elif ciclo == "Quincenal": seed = (fecha.day - 1) // 15 + (fecha.month * 2)
        else: seed = fecha.month # Mensual

        # Ordenar activos mezclando con el seed para rotar turnos fijos por periodo
        activos_ord = sorted(activos, key=lambda p: (hash(p) + seed) % 100)

        for _ in range(10): 
            p = activos_ord.pop(0); asignados[p]="T1"; carga[p]+=1
        for _ in range(10): 
            p = activos_ord.pop(0); asignados[p]="T2"; carga[p]+=1
        if activos_ord: 
            p = activos_ord.pop(0); asignados[p]="RELEVO"; carga[p]+=0.5

        for p in activos_ord:
            if compensado[p]>0: asignados[p]="COMPENSADO"; compensado[p]-=1
            else: asignados[p]="DISPONIBLE"

        for p in todos:
            filas.append({"Fecha": fecha, "Día": dia, "Sujeto": p, "Turno": asignados[p], "Festivo": "SI" if festivo else "NO"})
    return pd.DataFrame(filas)

# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
def main():
    st.sidebar.title("Configuración Central")
    tipo_personal = st.sidebar.radio("Tipo de Personal", ["Técnicos", "Abordaje"])
    modulo = st.radio("Módulo", ["Programador", "Parametrizador"], horizontal=True)

    if modulo == "Parametrizador":
        st.write("🔧 Configuración de parámetros del sistema OK.")
        return

    st.header(f"🚀 OPTIMIZADOR {tipo_personal.upper()}")
    
    col_f1, col_f2 = st.columns(2)
    inicio = col_f1.date_input("Inicio", date.today())
    fin = col_f2.date_input("Fin", date.today() + timedelta(days=30))

    descansos = {}
    ciclo = "Diario"

    if tipo_personal == "Técnicos":
        st.subheader("⚖️ Descanso de Ley (Técnicos)")
        cols = st.columns(len(GRUPOS_TEC))
        for i, g in enumerate(GRUPOS_TEC):
            descansos[g] = cols[i].selectbox(g, DIAS_ES, index=i, key=f"t_{g}")
    else:
        st.subheader("⚖️ Parametrización Abordaje (5 Grupos)")
        c_rot, c_des = st.columns([1,3])
        ciclo = c_rot.selectbox("Ciclo de Rotación", ["Diario", "Quincenal", "Mensual"])
        cols = c_des.columns(5)
        for i, g in enumerate(GRUPOS_ABO):
            descansos[g] = cols[i].selectbox(g, DIAS_ES, index=i, key=f"a_{g}")

    if st.button(f"🔥 Generar Malla {tipo_personal}"):
        if tipo_personal == "Técnicos":
            df = generar_logica_tecnicos(inicio, fin, descansos)
            st.session_state["malla_tec"] = df
            guardar_github(df, "malla_tecnicos.xlsx")
        else:
            df = generar_logica_abordaje(inicio, fin, descansos, ciclo)
            st.session_state["malla_abo"] = df
            guardar_github(df, "malla_abordaje.xlsx")
        st.success("Malla generada y guardada en GitHub.")

    # Mostrar Datos
    key = "malla_tec" if tipo_personal == "Técnicos" else "malla_abo"
    if key in st.session_state:
        df = st.session_state[key]
        pivot = df.pivot(index="Sujeto", columns="Fecha", values="Turno").sort_index(axis=1)

        st.subheader("📊 MALLA EDITABLE")
        editado = st.data_editor(pivot, use_container_width=True)

        if st.button("💾 Guardar Cambios"):
            df_edit = editado.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
            st.session_state[key] = df_edit
            guardar_github(df_edit, f"{key}.xlsx")
            st.success("Cambios aplicados correctamente.")

        col_err, col_view = st.columns([1, 2])
        errores, cobertura = auditoria(df, tipo_personal)
        with col_err:
            st.subheader("🚨 Auditoría")
            if errores: 
                for e in errores[:10]: st.error(e)
            else: st.success("Sin errores de cobertura.")
        with col_view:
            st.subheader("📋 Vista Operativa")
            st.dataframe(pivot.style.map(color_cell), use_container_width=True)

if __name__ == "__main__":
    main()
