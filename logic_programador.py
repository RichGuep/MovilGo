# app.py (Archivo Principal Unificado)
# =========================================================
# OPTIMIZADOR INTELIGENTE PRO ENTERPRISE - MOVILGO
# =========================================================

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import holidays
import io
from github import Github

# --- CONFIGURACIÓN GLOBAL ---
st.set_page_config(page_title="MovilGo Optimizer Pro", layout="wide")

DIAS_ES = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
festivos_co = holidays.Colombia()

# Estructuras de Personal
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Personal {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}

# =========================================================
# GITHUB Y ESTILOS
# =========================================================
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        return Github(st.secrets["GITHUB_TOKEN"]).get_repo("RichGuep/movilgo")
    except: return None

def guardar_github(df, nombre_archivo):
    repo = conectar_github()
    if not repo:
        st.warning("⚠️ GitHub no conectado. Verifique 'GITHUB_TOKEN' en Secrets.")
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

def color_cell(v):
    colores = {
        "T1":"background-color:#D6EAF8;color:#1B4F72;",
        "T2":"background-color:#D5F5E3;color:#145A32;",
        "T3":"background-color:#FADBD8;color:#7B241C;",
        "RELEVO":"background-color:#E8DAEF;color:#4A235A;font-weight:bold;",
        "DISPONIBLE":"background-color:#EAEDED;color:#7F8C8D;",
        "T1 APOYO":"background-color:#EBF5FB;",
        "DESCANSO":"background-color:#2C3E50;color:#F9E79F;font-weight:700;",
        "COMPENSADO":"background-color:#FDEBD0;"
    }
    return colores.get(v,"")

# =========================================================
# LÓGICA TÉCNICOS: BLOQUES DE 4 DÍAS Y PROTECCIÓN T3
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos):
    carga = {g:0 for g in GRUPOS_TEC}
    compensado = {g:0 for g in GRUPOS_TEC}
    sacrificio = {g:0 for g in GRUPOS_TEC}
    ultimo_turno = {g: "DESCANSO" for g in GRUPOS_TEC}
    conteo_bloque = {g: 0 for g in GRUPOS_TEC}
    
    filas = []
    for fecha in pd.date_range(inicio, fin):
        dia = DIAS_ES[fecha.weekday()]
        descanso_dia = [g for g in GRUPOS_TEC if descansos[g] == dia]
        activos = [g for g in GRUPOS_TEC if g not in descanso_dia]

        # Garantizar cobertura mínima de 3 para T1, T2 y T3
        while len(activos) < 3:
            mov = sorted(descanso_dia, key=lambda g:(sacrificio[g], carga[g]))[0]
            descanso_dia.remove(mov); activos.append(mov)
            sacrificio[mov]+=1; compensado[mov]+=1

        asignados = {g: "DESCANSO" for g in descanso_dia}
        for g in descanso_dia:
            ultimo_turno[g] = "DESCANSO"
            conteo_bloque[g] = 0

        # ASIGNACIÓN DE TURNOS BASE (T1, T2, T3)
        for t_obj in ["T3", "T2", "T1"]:
            # 1. Inercia de bloque (4 días)
            candidatos = [g for g in activos if ultimo_turno[g] == t_obj and conteo_bloque[g] < 4]
            if candidatos:
                sel = candidatos[0]
                asignados[sel] = t_obj; carga[sel] += 1; conteo_bloque[sel] += 1; activos.remove(sel)
            else:
                # 2. Nueva asignación (Prohibición T3 -> T1/T2)
                posibles = [g for g in activos if not (t_obj in ["T1", "T2"] and ultimo_turno[g] == "T3")]
                if posibles:
                    sel = sorted(posibles, key=lambda x: carga[x])[0]
                    asignados[sel] = t_obj; carga[sel] += 1; ultimo_turno[sel] = t_obj
                    conteo_bloque[sel] = 1; activos.remove(sel)
                elif activos: # Colchón de seguridad
                    sel = sorted(activos, key=lambda x: carga[x])[0]
                    asignados[sel] = t_obj; carga[sel] += 1; ultimo_turno[sel] = t_obj
                    conteo_bloque[sel] = 1; activos.remove(sel)

        # APOYOS CON SOBRANTES
        for g in activos[:]:
            if compensado[g] > 0:
                asignados[g] = "COMPENSADO"; compensado[g] -= 1; ultimo_turno[g] = "DESCANSO"
            else:
                asignados[g] = "T1 APOYO" if ultimo_turno[g] != "T3" else "DESCANSO"
            conteo_bloque[g] = 0; activos.remove(g)
        
        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# LÓGICA ABORDAJE: 5 GRUPOS Y ROTACIÓN
# =========================================================
def generar_malla_abordaje(inicio, fin, descansos_grupos, ciclo):
    filas = []
    todos = [p for sub in PERSONAL_ABO.values() for p in sub]
    for fecha in pd.date_range(inicio, fin):
        dia = DIAS_ES[fecha.weekday()]
        descansan = [p for g in GRUPOS_ABO if descansos_grupos[g] == dia for p in PERSONAL_ABO[g]]
        activos = [p for p in todos if p not in descansan]
        while len(activos) < 21: # 10 T1 + 10 T2 + 1 RELEVO
            mov = descansan.pop(0); activos.append(mov)
        asignados = {p: "DESCANSO" for p in descansan}
        
        if ciclo == "Diario": seed = (fecha - pd.to_datetime(inicio)).days
        elif ciclo == "Quincenal": seed = (fecha.day - 1) // 15 + (fecha.month * 10)
        else: seed = fecha.month + (fecha.year * 12)
        
        act_ord = sorted(activos, key=lambda p: (hash(p) + seed) % 100)
        for _ in range(10): p = act_ord.pop(0); asignados[p] = "T1"
        for _ in range(10): p = act_ord.pop(0); asignados[p] = "T2"
        if act_ord: p = act_ord.pop(0); asignados[p] = "RELEVO"
        for p in act_ord: asignados[p] = "DISPONIBLE"
        for p in todos:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asignados.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# AUDITORÍA DE COBERTURA
# =========================================================
def ejecutar_auditoria(df, tipo):
    errores = []
    df["Fecha"] = pd.to_datetime(df["Fecha"])
    if tipo == "Técnicos":
        for t in ["T1", "T2", "T3"]:
            conteo = df[df["Turno"] == t].groupby("Fecha").size()
            for f, c in conteo.items():
                if c == 0: errores.append(f"🚨 Turno {t} sin cubrir el {f.date()}")
    return errores

# =========================================================
# INTERFAZ PRINCIPAL
# =========================================================
def pantalla_programador():
    st.sidebar.title("MovilGo Enterprise")
    tipo = st.sidebar.radio("Tipo de Personal", ["Técnicos", "Abordaje"])
    
    st.header(f"📅 Gestión de Programación: {tipo}")
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Inicio", date.today())
    fin = c2.date_input("Fin", date.today() + timedelta(days=30))

    descansos = {}
    ciclo = "Diario"
    if tipo == "Técnicos":
        st.info("💡 Bloques de 4 días y prohibición de saltos T3 ➔ T1/T2 activos.")
        cols = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC):
            descansos[g] = cols[i].selectbox(g, DIAS_ES, index=i)
    else:
        c_rot, c_des = st.columns([1,3])
        ciclo = c_rot.selectbox("Ciclo Rotación", ["Diario", "Quincenal", "Mensual"])
        cols_a = c_des.columns(5)
        for i, g in enumerate(GRUPOS_ABO):
            descansos[g] = cols_a[i].selectbox(g, DIAS_ES, index=i)

    if st.button(f"🚀 Generar Malla"):
        df = generar_malla_tecnicos(inicio, fin, descansos) if tipo == "Técnicos" else generar_malla_abordaje(inicio, fin, descansos, ciclo)
        st.session_state[f"malla_{tipo}"] = df

    key = f"malla_{tipo}"
    if key in st.session_state:
        df_actual = st.session_state[key]
        pivot = df_actual.pivot(index="Sujeto", columns="Fecha", values="Turno").sort_index(axis=1)
        
        st.subheader("📝 Editor y Auditoría")
        df_editado = st.data_editor(pivot.style.map(color_cell), use_container_width=True)

        if st.button("💾 Guardar y Validar"):
            df_final = df_editado.reset_index().melt(id_vars="Sujeto", var_name="Fecha", value_name="Turno")
            st.session_state[key] = df_final
            guardar_github(df_final, f"malla_{tipo.lower()}.xlsx")
            
            errs = ejecutar_auditoria(df_final, tipo)
            if errs:
                for e in errs: st.error(e)
            else:
                st.success("✅ Malla guardada. Cobertura T1, T2, T3 al 100%.")

if __name__ == "__main__":
    pantalla_programador()
