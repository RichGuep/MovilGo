# logic_programador_unificado.py
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
# CONFIGURACIÓN GLOBAL Y CONSTANTES
# =========================================================
DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
festivos_co = holidays.Colombia()

# Config Técnicos (Existente)
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
TURNOS_TEC = ["T1","T2","T3","T1 APOYO","T2 APOYO","DESCANSO","COMPENSADO"]

# Config Abordaje (Nuevo)
PERSONAL_ABO = [f"Abordaje {i+1:02d}" for i in range(25)]
TURNOS_ABO = ["T1", "T2", "RELEVO", "DISPONIBLE", "DESCANSO", "COMPENSADO"]

# =========================================================
# GITHUB (MANTENIDO)
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except:
        return None

def guardar_github(df, nombre_archivo="malla_historica.xlsx"):
    repo = conectar_github()
    if not repo: return

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False)
    data = buffer.getvalue()

    try:
        file = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, f"update {datetime.now()}", data, file.sha)
    except:
        repo.create_file(nombre_archivo, "create", data)

# =========================================================
# COLORES (AMPLIADO PARA ABORDAJE)
# =========================================================
def color_cell(v):
    colores = {
        "T1":"background-color:#D6EAF8;color:#1B4F72;",
        "T2":"background-color:#D5F5E3;color:#145A32;",
        "T3":"background-color:#FADBD8;color:#7B241C;",
        "T1 APOYO":"background-color:#EBF5FB;",
        "T2 APOYO":"background-color:#EAF2F8;",
        "RELEVO":"background-color:#E8DAEF;color:#4A235A;font-weight:600;",
        "DISPONIBLE":"background-color:#EAEDED;color:#7F8C8D;",
        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;font-weight:700;",
        "COMPENSADO":"background-color:#FDEBD0;"
    }
    return colores.get(v,"")

# =========================================================
# AUDITORÍA (UNIFICADA)
# =========================================================
def auditoria(df, tipo="Técnicos"):
    errores = []
    df = df.copy()
    df["Fecha"] = pd.to_datetime(df["Fecha"])

    if tipo == "Técnicos":
        cobertura = df[df["Turno"].isin(["T1","T2","T3"])].groupby("Fecha").size()
        for f,c in cobertura.items():
            if c < 3: errores.append(f"❌ Cobertura incompleta {f.date()} ({c}/3)")
    else:
        # Auditoría Abordaje (10 T1, 10 T2)
        t1 = df[df["Turno"] == "T1"].groupby("Fecha").size()
        t2 = df[df["Turno"] == "T2"].groupby("Fecha").size()
        cobertura = t1 + t2 # Solo para el gráfico
        for f in t1.index:
            if t1[f] < 10: errores.append(f"❌ Falta T1 el {f.date()} ({t1[f]}/10)")
            if t2[f] < 10: errores.append(f"❌ Falta T2 el {f.date()} ({t2[f]}/10)")

    return errores, cobertura

# =========================================================
# LÓGICA GENERADORA TÉCNICOS (TU LÓGICA ORIGINAL)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descanso):
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
        descanso_dia = [g for g in GRUPOS_TEC if descanso[g]==dia]
        activos = [g for g in GRUPOS_TEC if g not in descanso_dia]

        while len(activos) < 3:
            mov = sorted(descanso_dia, key=lambda g:(sacrificio[g],carga[g]))[0]
            descanso_dia.remove(mov)
            activos.append(mov)
            sacrificio[mov]+=1
            compensado[mov]+=1

        for g in descanso_dia: asignados[g]="DESCANSO"

        for turno in ["T1","T2","T3"]:
            sel = sorted(activos, key=lambda g:(carga[g],conteo[g][turno]))[0]
            asignados[sel]=turno
            carga[sel]+=1
            conteo[sel][turno]+=1
            activos.remove(sel)

        for g in activos:
            if compensado[g]>0:
                asignados[g]="COMPENSADO"; compensado[g]-=1
            else: asignados[g]="T1 APOYO"

        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Día": dia, "Grupo": g, "Turno": asignados[g], "Festivo": "SI" if festivo else "NO"})
    
    return pd.DataFrame(filas)

# =========================================================
# LÓGICA GENERADORA ABORDAJE (NUEVA LÓGICA ESPEJO)
# =========================================================
def generar_malla_abordaje(inicio, fin, descanso):
    carga = {p:0 for p in PERSONAL_ABO}
    compensado = {p:0 for p in PERSONAL_ABO}
    sacrificio = {p:0 for p in PERSONAL_ABO}
    filas = []
    fechas = pd.date_range(inicio, fin)

    for fecha in fechas:
        dia = DIAS_ES[fecha.weekday()]
        festivo = fecha.date() in festivos_co
        asignados = {}
        descanso_dia = [p for p in PERSONAL_ABO if descanso[p]==dia]
        activos = [p for p in PERSONAL_ABO if p not in descanso_dia]

        # Garantizar mínimo 21 activos (10 T1 + 10 T2 + 1 Relevo)
        while len(activos) < 21:
            mov = sorted(descanso_dia, key=lambda p:(sacrificio[p],carga[p]))[0]
            descanso_dia.remove(mov)
            activos.append(mov)
            sacrificio[mov]+=1
            compensado[mov]+=1

        for p in descanso_dia: asignados[p]="DESCANSO"

        # Asignar 10 T1
        for _ in range(10):
            sel = sorted(activos, key=lambda p: carga[p])[0]
            asignados[sel] = "T1"; carga[sel]+=1; activos.remove(sel)
        
        # Asignar 10 T2
        for _ in range(10):
            sel = sorted(activos, key=lambda p: carga[p])[0]
            asignados[sel] = "T2"; carga[sel]+=1; activos.remove(sel)

        # Asignar 1 Relevo
        if activos:
            sel = sorted(activos, key=lambda p: carga[p])[0]
            asignados[sel] = "RELEVO"; carga[sel]+=1; activos.remove(sel)

        # Resto: Compensado o Disponible
        for p in activos:
            if compensado[p]>0:
                asignados[p]="COMPENSADO"; compensado[p]-=1
            else: asignados[p]="DISPONIBLE"

        for p in PERSONAL_ABO:
            filas.append({"Fecha": fecha, "Día": dia, "Grupo": p, "Turno": asignados[p], "Festivo": "SI" if festivo else "NO"})
    
    return pd.DataFrame(filas)

# =========================================================
# INTERFAZ (MANTENIENDO TU ESTRUCTURA ORIGINAL)
# =========================================================
def pantalla_programador():
    st.title("💼 Gestión de Personal MovilGo")
    
    # Selector de Personal (Para que no se mezclen)
    tipo_personal = st.sidebar.selectbox("Seleccione Personal", ["Técnicos", "Abordaje"])
    op = st.radio("Módulo",["Programador","Parametrizador"],horizontal=True)

    if op=="Parametrizador":
        st.info("Configuraciones avanzadas de parámetros próximamente.")
        return

    # --- INPUTS ---
    st.header(f"🚀 OPTIMIZADOR {tipo_personal.upper()}")
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Inicio", date.today(), key="ini")
    fin = c2.date_input("Fin", date.today()+timedelta(days=30), key="fin")

    st.subheader("⚖️ Configuración de Descansos")
    descanso_config = {}
    
    if tipo_personal == "Técnicos":
        cols = st.columns(len(GRUPOS_TEC))
        for i,g in enumerate(GRUPOS_TEC):
            descanso_config[g] = cols[i].selectbox(g, DIAS_ES, index=i, key=f"d_{g}")
    else:
        # Para 25 personas de abordaje, usamos un expander para no llenar la pantalla
        with st.expander("Ver lista de personal de abordaje"):
            cols = st.columns(5)
            for i,p in enumerate(PERSONAL_ABO):
                descanso_config[p] = cols[i%5].selectbox(p, DIAS_ES, index=i%7, key=f"d_{p}")

    # --- GENERACIÓN ---
    if st.button(f"🚀 Generar malla {tipo_personal}"):
        if tipo_personal == "Técnicos":
            df = generar_malla_tecnicos(inicio, fin, descanso_config)
            st.session_state["malla_tec"] = df
            guardar_github(df, "malla_tecnicos.xlsx")
        else:
            df = generar_malla_abordaje(inicio, fin, descanso_config)
            st.session_state["malla_abo"] = df
            guardar_github(df, "malla_abordaje.xlsx")
        st.success(f"Malla de {tipo_personal} generada.")

    # --- VISTA Y EDICIÓN ---
    session_key = "malla_tec" if tipo_personal == "Técnicos" else "malla_abo"
    
    if session_key in st.session_state:
        df = st.session_state[session_key]
        st.subheader(f"📊 MALLA {tipo_personal.upper()} (EDITABLE)")
        
        pivot = df.pivot(index="Grupo", columns="Fecha", values="Turno").sort_index(axis=1)
        edit = st.data_editor(pivot, use_container_width=True, key=f"ed_{session_key}")

        if st.button("💾 Guardar cambios"):
            df_edit = edit.reset_index().melt(id_vars="Grupo", var_name="Fecha", value_name="Turno")
            df_edit["Fecha"] = pd.to_datetime(df_edit["Fecha"])
            st.session_state[session_key] = df_edit
            guardar_github(df_edit, f"{session_key}.xlsx")
            st.success("Cambios sincronizados.")

        # Auditoría
        col1, col2 = st.columns([2,1])
        with col2:
            st.subheader("🚨 Auditoría")
            errores, cobertura = auditoria(df, tipo_personal)
            if errores:
                for e in errores[:15]: st.error(e)
            else: st.success("Sin errores detectados")
            st.line_chart(cobertura)

        with col1:
            st.subheader("📋 Vista operativa")
            st.dataframe(pivot.style.map(color_cell), use_container_width=True)

if __name__ == "__main__":
    pantalla_programador()
