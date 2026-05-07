import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- DICCIONARIO PARA ESPAÑOL ---
DIAS_ES = {
    "Monday": "Lun", "Tuesday": "Mar", "Wednesday": "Mié",
    "Thursday": "Jue", "Friday": "Vie", "Saturday": "Sáb", "Sunday": "Dom"
}

# --- CONEXIÓN ---
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("Falta el token GITHUB_TOKEN en los Secrets.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error conexión GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
    """Busca el cierre del periodo anterior para dar continuidad."""
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df_hist = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_hist['Fecha_Raw'] = pd.to_datetime(df_hist['Fecha_Raw'])
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw', ascending=False)
            if not regs.empty:
                u = regs.iloc[0]
                estado[g] = {
                    "u": u['Turno'], 
                    "n": int(u.get('Noches_Acum', 0)) if u['Turno'] == "T3" else 0,
                    "d": int(u.get('Deuda_Compensatorio', 0))
                }
            else:
                estado[g] = {"u": "DESC", "n": 0, "d": 0}
        return estado
    except:
        return {g: {"u": "DESC", "n": 0, "d": 0} for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]}

# --- REGLAS DE SALUD Y FORMATO ---
def es_cambio_saludable(ayer, hoy):
    """Evita saltos peligrosos como T3 (Noche) a T1 (Mañana)."""
    if ayer in ["DESC", "COMP", "OFF", "-"] or hoy in ["DESC", "COMP", "OFF", "-"]:
        return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def obtener_horario(turno):
    h = {
        "T1": ("06:00", "14:00"), "T2": ("14:00", "22:00"), "T3": ("22:00", "06:00"),
        "DESC": ("LIBRE", "LIBRE"), "COMP": ("LIBRE", "LIBRE")
    }
    return h.get(turno, ("-", "-"))

def color_t(val):
    c = {"T1": "#1f77b4", "T2": "#2ca02c", "T3": "#4d4d4d", "DESC": "#d62728", "COMP": "#ff7f0e", "OFF": "#d62728"}
    bg = c.get(val, "#ffffff")
    text = "white" if val in c else "black"
    return f'background-color: {bg}; color: {text}; font-weight: bold; border: 1px solid #cecece; text-align: center;'

def aplicar_estilos(df):
    """Pinta los colores en las tablas de Streamlit."""
    return df.style.map(color_t)

# --- MOTOR DE GENERACIÓN ---
def generar_malla_base(f_ini, f_fin, repo):
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    estado_ayer = obtener_ultimo_estado_github(repo)
    lista_fechas = [f_ini + timedelta(days=x) for x in range((f_fin - f_ini).days + 1)]
    resultados = []
    
    mem_t = {g: estado_ayer[g]["u"] for g in grupos_n}
    mem_n = {g: estado_ayer[g]["n"] for g in grupos_n}
    deudas = {g: estado_ayer[g]["d"] for g in grupos_n}
    co_h = holidays.Colombia(years=[2024, 2025, 2026])

    for fecha in lista_fechas:
        fecha_dt = pd.to_datetime(fecha)
        es_fest = fecha_dt in co_h
        dia_es = DIAS_ES.get(fecha_dt.strftime('%A'), fecha_dt.strftime('%A')[:3])
        col_name = f"{dia_es} {fecha_dt.strftime('%d/%m')}{' 🇨🇴' if es_fest else ''}"

        dia_idx = fecha_dt.weekday()
        sem_iso = fecha_dt.isocalendar()[1]

        libranza = None
        if dia_idx == 5: # Sábado
            libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
            deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
        elif dia_idx == 6: # Domingo
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

        for g in grupos_n:
            t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
            resultados.append({
                "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                "Fecha_Raw": fecha_dt, "Noches_Acum": mem_n[g] + 1 if t_f == "T3" else 0,
                "Deuda_Compensatorio": deudas[g]
            })
            mem_t[g] = t_f; mem_n[g] = (mem_n[g] + 1 if t_f == "T3" else 0)

    return pd.DataFrame(resultados)
