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

# Datos Maestros
GRUPOS_TEC = ["Grupo 1","Grupo 2","Grupo 3","Grupo 4"]
GRUPOS_ABO = ["Abordaje G1", "Abordaje G2", "Abordaje G3", "Abordaje G4", "Abordaje G5"]
PERSONAL_ABO = {g: [f"Personal {g[-2:]}-{i+1:02d}" for i in range(5)] for g in GRUPOS_ABO}

# =========================================================
# SOPORTE TÉCNICO (GITHUB / ESTILOS)
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
# LÓGICA DE GENERACIÓN - TÉCNICOS (PROTECCIÓN CIRCADIANA)
# =========================================================
def generar_malla_tecnicos(inicio, fin, descansos):
    carga = {g:0 for g in GRUPOS_TEC}
    compensado = {g:0 for g in GRUPOS_TEC}
    sacrificio = {g:0 for g in GRUPOS_TEC}
    ultimo_turno = {g: None for g in GRUPOS_TEC}
    conteo_bloque = {g: 0 for g in GRUPOS_TEC}
    
    filas = []
    fechas = pd.date_range(inicio, fin)

    for fecha in fechas:
        dia = DIAS_ES[fecha.weekday()]
        festivo = fecha.date() in festivos_co
        asignados = {}
        
        descanso_dia = [g for g in GRUPOS_TEC if descansos[g] == dia]
        activos = [g for g in GRUPOS_TEC if g not in descanso_dia]

        # Garantizar cobertura 3 personas (Sacrificio de descanso si es necesario)
        while len(activos) < 3:
            mov = sorted(descanso_dia, key=lambda g:(sacrificio[g], carga[g]))[0]
            descanso_dia.remove(mov); activos.append(mov)
            sacrificio[mov]+=1; compensado[mov]+=1

        # 1. Asignar Descansos Reales
        for g in descanso_dia:
            asignados[g] = "DESCANSO"
            ultimo_turno[g] = "DESCANSO" # El descanso habilita cualquier turno mañana
            conteo_bloque[g] = 0

        # 2. Mantener Inercia (Bloques de 4 días) respetando prohibición T3 -> T1/T2
        for turno_target in ["T3", "T2", "T1"]:
            # Solo candidatos que ya venían en ese turno y no han cumplido el bloque
            candidatos = [g for g in activos if ultimo_turno[g] == turno_target and conteo_bloque[g] < 4]
            for g in candidatos:
                if g in activos:
                    asignados[g] = turno_target
                    carga[g] += 1
                    conteo_bloque[g] += 1
                    activos.remove(g)

        # 3. Asignar Turnos Restantes con restricción de SALTO ASCENDENTE
        # Se prioriza T3 porque es el más restrictivo
        for turno_target in ["T3", "T2", "T1"]:
            if turno_target not in [v for k,v in asignados.items() if k in GRUPOS_TEC]:
                if activos:
                    # Filtrar activos que PUEDEN tomar este turno
                    # Si el turno es T1 o T2, el último turno NO puede haber sido T3
                    posibles = []
                    for g in activos:
                        if turno_target in ["T1", "T2"] and ultimo_turno[g] == "T3":
                            continue # BLOQUEADO: Requiere descanso
                        posibles.append(g)
                    
                    if posibles:
                        sel = sorted(posibles, key=lambda x: carga[x])[0]
                        asignados[sel] = turno_target
                        carga[sel] += 1
                        ultimo_turno[sel] = turno_target
                        conteo_bloque[sel] = 1
                        activos.remove(sel)

        # 4. Apoyos y Compensados (Si sobran activos)
        for g in activos:
            if compensado[g] > 0:
                asignados[g] = "COMPENSADO"
                compensado[g] -= 1
                ultimo_turno[g] = "DESCANSO" # El compensado actúa como descanso
            else:
                # Si venía de T3, no puede hacer T1 APOYO (que es mañana)
                if ultimo_turno[g] == "T3":
                    asignados[g] = "DESCANSO" # Forzamos descanso por salud si no hay más hueco
                    sacrificio[g] -= 1 # No cuenta como sacrificio, es salud
                else:
                    asignados[g] = "T1 APOYO"
            activos.remove(g)

        for g in GRUPOS_TEC:
            filas.append({"Fecha": fecha, "Sujeto": g, "Turno": asignados.get(g, "T1 APOYO")})
            
    return pd.DataFrame(filas)

# =========================================================
# LÓGICA DE GENERACIÓN - ABORDAJE (MANTENIDA)
# =========================================================
def generar_malla_abordaje(inicio, fin, descansos_grupos, ciclo):
    filas = []
    fechas = pd.date_range(inicio, fin)
    todos = [p for sub in PERSONAL_ABO.values() for p in sub]
    carga = {p:0 for p in todos}
    for fecha in fechas:
        dia = DIAS_ES[fecha.weekday()]
        descansan_hoy = [p for g in GRUPOS_ABO if descansos_grupos[g] == dia for p in PERSONAL_ABO[g]]
        activos = [p for p in todos if p not in descansan_hoy]
        
        asignados = {p: "DESCANSO" for p in descansan_hoy}
        
        if ciclo == "Diario": seed = (fecha - pd.to_datetime(inicio)).days
        elif ciclo == "Quincenal": seed = (fecha.day - 1) // 15 + (fecha.month * 10)
        else: seed = fecha.month + (fecha.year * 12)
        
        activos_ord = sorted(activos, key=lambda p: (hash(p) + seed) % 100)
        
        # 10 T1, 10 T2, 1 Relevo
        for _ in range(min(10, len(activos_ord))): p = activos_ord.pop(0); asignados[p]="T1"
        for _ in range(min(10, len(activos_ord))): p = activos_ord.pop(0); asignados[p]="T2"
        if activos_ord: p = activos_ord.pop(0); asignados[p]="RELEVO"
        for p in activos_ord: asignados[p]="DISPONIBLE"
        
        for p in todos:
            filas.append({"Fecha": fecha, "Sujeto": p, "Turno": asignados.get(p, "DESCANSO")})
    return pd.DataFrame(filas)

# =========================================================
# INTERFAZ (UI)
# =========================================================
def pantalla_programador():
    st.sidebar.title("MovilGo Pro")
    tipo = st.sidebar.radio("Personal", ["Técnicos", "Abordaje"])
    
    st.header(f"📅 Programación de {tipo}")
    c1, c2 = st.columns(2)
    inicio = c1.date_input("Desde", date.today())
    fin = c2.date_input("Hasta", date.today() + timedelta(days=30))

    descansos = {}
    ciclo = "Diario"

    if tipo == "Técnicos":
        st.warning("⚠️ Restricción Bio-Segura: El paso de T3 a T1/T2 está bloqueado. Solo se permite tras un Descanso o Compensado.")
        cols = st.columns(4)
        for i, g in enumerate(GRUPOS_TEC):
            descansos[g] = cols[i].selectbox(g, DIAS_ES, index=i)
    else:
        c_rot, c_des = st.columns([1,3])
        ciclo = c_rot.selectbox("Rotación", ["Diario", "Quincenal", "Mensual"])
        cols_a = c_des.columns(5)
        for i, g in enumerate(GRUPOS_ABO):
            descansos[g] = cols_a[i].selectbox(g, DIAS_ES, index=i)

    if st.button(f"Generar Malla"):
        if tipo == "Técnicos":
            df = generar_malla_tecnicos(inicio, fin, descansos)
            st.session_state["m_tec"] = df
        else:
            df = generar_malla_abordaje(inicio, fin, descansos, ciclo)
            st.session_state["m_abo"] = df
        st.success("Malla generada.")

    key = "m_tec" if tipo == "Técnicos" else "m_abo"
    if key in st.session_state:
        df = st.session_state[key]
        pivot = df.pivot(index="Sujeto", columns="Fecha", values="Turno")
        st.data_editor(pivot.style.map(color_cell), use_container_width=True)
        
        if st.button("💾 Guardar"):
            guardar_github(df, f"malla_{tipo.lower()}.xlsx")
            st.toast("Archivo actualizado en GitHub")

if __name__ == "__main__":
    pantalla_programador()
