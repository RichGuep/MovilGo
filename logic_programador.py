import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. CONEXIÓN Y PERSISTENCIA ---
def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("Falta GITHUB_TOKEN en los Secrets de Streamlit.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error de conexión GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
    """Busca el último estado registrado para dar continuidad a la rotación."""
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

# --- 2. REGLAS DE NEGOCIO Y SALUD ---
def es_cambio_saludable(ayer, hoy):
    """Evita saltos prohibidos: No se puede pasar de Noche (T3) a Mañana (T1) sin descanso."""
    if ayer in ["DESC", "COMP", "OFF", "-"] or hoy in ["DESC", "COMP", "OFF", "-"]: 
        return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def obtener_horario(turno):
    """Retorna horas de entrada y salida para el módulo de nómina."""
    h = {
        "T1": ("06:00", "14:00"),
        "T2": ("14:00", "22:00"),
        "T3": ("22:00", "06:00"),
        "DESC": ("OFF", "OFF"),
        "COMP": ("OFF", "OFF")
    }
    return h.get(turno, ("-", "-"))

# --- 3. SISTEMA DE COLORES (STREAMLIT) ---
def color_t(val):
    """Aplica el diseño visual a las celdas."""
    c = {
        "T1": "#1f77b4", # Azul
        "T2": "#2ca02c", # Verde
        "T3": "#4d4d4d", # Gris (Noche)
        "DESC": "#d62728", # Rojo
        "COMP": "#ff7f0e", # Naranja
        "OFF": "#d62728"
    }
    bg = c.get(val, "#ffffff")
    text = "white" if val in c else "black"
    return f'background-color: {bg}; color: {text}; font-weight: bold; border: 1px solid #cecece; text-align: center;'

def aplicar_estilos(df):
    """Transforma un DataFrame normal en uno con colores para Streamlit."""
    return df.style.map(color_t)

# --- 4. MOTOR DE GENERACIÓN INTELIGENTE ---
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
        dia_idx = fecha_dt.weekday()
        sem_iso = fecha_dt.isocalendar()[1]
        es_fest = fecha_dt in co_h
        col_name = f"{fecha_dt.strftime('%a %d/%m')}{' 🇨🇴' if es_fest else ''}"

        # Lógica de Libranza (Sábados/Domingos)
        libranza = None
        if dia_idx == 5: # Sábado
            libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
            deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
        elif dia_idx == 6: # Domingo
            libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
            deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
        else:
            # Cobro de compensatorios pendientes entre semana
            for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                if deudas[g] > 0 and mem_t[g] != "T3":
                    libranza = g; deudas[g] -= 1; break

        activos = [g for g in grupos_n if g != libranza]
        turnos_hoy = {}
        
        # Asignación sugerida según semana
        for g in activos:
            idx_g = grupos_n.index(g)
            t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
            
            # Validación de salud
            if not es_cambio_saludable(mem_t[g], t_sug): 
                t_sug = mem_t[g]
            
            # Límite de noches consecutivas (6 noches máx)
            if mem_n[g] >= 6 and t_sug == "T3": 
                t_sug = "T1"
                
            turnos_hoy[g] = t_sug

        # Garantizar cobertura T1, T2, T3
        for tr in ["T1", "T2", "T3"]:
            if tr not in turnos_hoy.values():
                for gf in activos:
                    if list(turnos_hoy.values()).count(turnos_hoy[gf]) > 1:
                        if es_cambio_saludable(mem_t[gf], tr):
                            turnos_hoy[gf] = tr; break
        
        for g in grupos_n:
            t_f = ("DESC" if dia_idx >= 5 else "COMP") if g == libranza else turnos_hoy.get(g, "T1")
            n_a = mem_n[g] + 1 if t_f == "T3" else 0
            
            resultados.append({
                "Grupo": g, "Fecha_Col": col_name, "Turno": t_f, 
                "Fecha_Raw": fecha_dt, "Noches_Acum": n_a,
                "Deuda_Compensatorio": deudas[g]
            })
            mem_t[g] = t_f; mem_n[g] = n_a

    return pd.DataFrame(resultados)
