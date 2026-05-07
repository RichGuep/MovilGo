import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- CONSTANTES Y CONFIGURACIÓN ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png"

# --- CONEXIÓN GITHUB ---
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets: return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except: return None

def cargar_excel(nombre_archivo):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        contents = repo.get_contents(nombre_archivo)
        df = pd.read_excel(io.BytesIO(contents.decoded_content))
        if 'Fecha_Raw' in df.columns:
            df['Fecha_Raw'] = pd.to_datetime(df['Fecha_Raw'])
        return df
    except: return pd.DataFrame()

def guardar_excel(df_nuevo, nombre_archivo, mensaje):
    repo = conectar_github()
    if not repo: return
    try:
        try:
            contents = repo.get_contents(nombre_archivo)
            df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
            df_previo['Fecha_Raw'] = pd.to_datetime(df_previo['Fecha_Raw'])
            df_final = pd.concat([df_previo, df_nuevo]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
            sha = contents.sha
        except:
            df_final = df_nuevo
            sha = None

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        if sha: repo.update_file(nombre_archivo, mensaje, output.getvalue(), sha)
        else: repo.create_file(nombre_archivo, mensaje, output.getvalue())
    except Exception as e:
        st.error(f"Error al guardar en GitHub: {e}")

# --- REGLAS DE NEGOCIO ---
def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP"] or hoy in ["DESC", "COMP"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_turnos(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#7f7f7f", "DESC": "#ff4b4b", "COMP": "#ffa500"}
    return f'background-color: {c.get(val, "#31333F")}; color: white; font-weight: bold;'

def obtener_ultimo_estado(repo):
    df_hist = cargar_excel("malla_historica.xlsx")
    grupos = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    if df_hist.empty: return {g: {"u": "DESC", "n": 0, "d": 0} for g in grupos}
    estado = {}
    for g in grupos:
        regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw')
        if not regs.empty:
            u = regs.iloc[-1]
            estado[g] = {
                "u": u['Turno'], 
                "n": int(u.get('Noches_Acum', 0)) if u['Turno'] == "T3" else 0,
                "d": int(u.get('Deuda_Compensatorio', 0))
            }
        else: estado[g] = {"u": "DESC", "n": 0, "d": 0}
    return estado

def generar_malla_logica(f_ini, f_fin):
    repo = conectar_github()
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    estado_ayer = obtener_ultimo_estado(repo)
    
    lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
    resultados = []
    
    mem_t = {g: estado_ayer[g]["u"] for g in grupos_n}
    mem_n = {g: estado_ayer[g]["n"] for g in grupos_n}
    deudas = {g: estado_ayer[g]["d"] for g in grupos_n}
    co_h = holidays.Colombia(years=[2024, 2025, 2026])

    for fecha in lista_fechas:
        fecha_dt = pd.to_datetime(fecha)
        dia_idx = fecha_dt.weekday()
        sem_iso = fecha_dt.isocalendar()[1]
        es_fest = fecha_dt in co_h
        col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

        libranza = None
        if dia_idx == 5:
            libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
            deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
        elif dia_idx == 6:
            libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
            deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
        else:
            for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                if deudas[g] > 0 and mem_t[g] != "T3":
                    libranza = g; deudas[g] -= 1; break

        activos = [g for g in grupos_n if g != libranza]
        turnos_hoy = {}
        for g in activos:
            idx_g = grupos_n.index(g)
            t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
            if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
            if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
            turnos_hoy[g] = t_sug

        for tr in ["T1", "T2", "T3"]:
            if tr not in turnos_hoy.values():
                for gf in sorted(activos, key=lambda x: (mem_t[x] == "T3")):
                    if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                        if es_cambio_saludable(mem_t[gf], tr):
                            turnos_hoy[gf] = tr; break
        
        for g in grupos_n:
            t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
            n_a = mem_n[g] + 1 if t_f == "T3" else 0
            resultados.append({
                "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                "Fecha_Raw": fecha_dt, "Noches_Acum": n_a, "Deuda_Compensatorio": deudas[g]
            })
            mem_t[g] = t_f; mem_n[g] = n_a
            
    return pd.DataFrame(resultados)
