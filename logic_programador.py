import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. CONFIGURACIÓN Y CONSTANTES VISUALES ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"
LOGO_CABLE = f"{URL_BASE}logo_empresa_2.png" 

# --- 2. CONEXIÓN Y PERSISTENCIA GITHUB ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token GITHUB_TOKEN no configurado.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
    """Recupera el cierre del periodo anterior para dar continuidad."""
    try:
        contents = repo.get_contents("malla_historica.xlsx")
        df_hist = pd.read_excel(io.BytesIO(contents.decoded_content))
        df_hist['Fecha_Raw'] = pd.to_datetime(df_hist['Fecha_Raw'])
        estado = {}
        for g in ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]:
            regs = df_hist[df_hist['Grupo'] == g].sort_values('Fecha_Raw', ascending=False)
            if not regs.empty:
                u = regs.iloc[0] # Último registro en el tiempo
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

def guardar_malla_en_historico(df_nueva):
    """Guarda en GitHub unificando con lo existente sin duplicar fechas."""
    repo = conectar_github()
    if not repo: return
    try:
        try:
            contents = repo.get_contents("malla_historica.xlsx")
            df_previo = pd.read_excel(io.BytesIO(contents.decoded_content))
            df_previo['Fecha_Raw'] = pd.to_datetime(df_previo['Fecha_Raw'])
            df_nueva['Fecha_Raw'] = pd.to_datetime(df_nueva['Fecha_Raw'])
            df_final = pd.concat([df_previo, df_nueva]).drop_duplicates(subset=['Grupo', 'Fecha_Raw'], keep='last')
        except:
            df_final = df_nueva

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_final.to_excel(writer, index=False)
        
        contents = repo.get_contents("malla_historica.xlsx")
        repo.update_file("malla_historica.xlsx", "Sincronización Malla Logic", output.getvalue(), contents.sha)
        st.success("✅ Memoria de rotación actualizada en GitHub.")
    except Exception as e:
        st.error(f"Error al guardar: {e}")

def cargar_excel(nombre_archivo):
    repo = conectar_github()
    if not repo: return pd.DataFrame()
    try:
        contents = repo.get_contents(nombre_archivo)
        return pd.read_excel(io.BytesIO(contents.decoded_content))
    except:
        return pd.DataFrame()

def guardar_excel_generico(df, nombre_archivo, mensaje):
    repo = conectar_github()
    if not repo: return
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    try:
        contents = repo.get_contents(nombre_archivo)
        repo.update_file(nombre_archivo, mensaje, output.getvalue(), contents.sha)
    except:
        repo.create_file(nombre_archivo, mensaje, output.getvalue())

# --- 3. LÓGICA DE SALUD Y FORMATO ---

def es_cambio_saludable(ayer, hoy):
    """Verifica la jerarquía de turnos para evitar saltos prohibidos."""
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    """Aplica colores corporativos con alto contraste."""
    c = {
        "T1": "#1f77b4", # Azul
        "T2": "#2ca02c", # Verde
        "T3": "#4d4d4d", # Gris oscuro (Noche)
        "DESC": "#d62728", # Rojo
        "COMP": "#ff7f0e", # Naranja
        "OFF": "#d62728"
    }
    bg = c.get(val, "#ffffff")
    text = "white" if val in c else "black"
    return f'background-color: {bg}; color: {text}; font-weight: bold; border: 1px solid #444; text-align: center;'

def obtener_horario(turno):
    """Define las horas de entrada y salida para nómina."""
    h = {
        "T1": ("06:00", "14:00"),
        "T2": ("14:00", "22:00"),
        "T3": ("22:00", "06:00"),
        "DESC": ("OFF", "OFF"),
        "COMP": ("OFF", "OFF")
    }
    return h.get(turno, ("-", "-"))

# --- 4. MOTOR DE GENERACIÓN INTELIGENTE ---

def generar_malla_base(f_ini, f_fin, repo):
    """Ejecuta el algoritmo de rotación 24/7 considerando festivos y continuidad."""
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

        # Lógica de Libranza (Sábados y Domingos)
        libranza = None
        if dia_idx == 5: # Sábado
            libranza = "Grupo 1" if sem_iso % 2 == 0 else "Grupo 2"
            deudas["Grupo 2" if sem_iso % 2 == 0 else "Grupo 1"] += 1
        elif dia_idx == 6: # Domingo
            libranza = "Grupo 3" if sem_iso % 2 == 0 else "Grupo 4"
            deudas["Grupo 4" if sem_iso % 2 == 0 else "Grupo 3"] += 1
        else:
            # Cobro de compensatorios acumulados
            for g in sorted(grupos_n, key=lambda x: deudas[x], reverse=True):
                if deudas[g] > 0 and mem_t[g] != "T3":
                    libranza = g; deudas[g] -= 1; break

        # Asignación de Turnos Activos
        activos = [g for g in grupos_n if g != libranza]
        turnos_hoy = {}
        for g in activos:
            idx_g = grupos_n.index(g)
            t_sug = ["T1", "T2", "T3"][(idx_g + sem_iso) % 3]
            if not es_cambio_saludable(mem_t[g], t_sug): t_sug = mem_t[g]
            if mem_n[g] >= 6 and t_sug == "T3": t_sug = "T1"
            turnos_hoy[g] = t_sug

        # Motor de Cobertura (Garantizar T1, T2, T3)
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
                "Fecha_Raw": fecha_dt, "Noches_Acum": n_a,
                "Deuda_Compensatorio": deudas[g]
            })
            mem_t[g] = t_f; mem_n[g] = n_a

    return pd.DataFrame(resultados)

# --- 5. VALIDADOR DE NOVEDADES ---

# --- VALIDADOR CORREGIDO (FILTRADO POR RANGO) ---
def validar_malla_saludable(df_res, f_ini, f_fin):
    """Analiza SOLO el rango seleccionado para evitar alertas de otros meses."""
    alertas = []
    if df_res is None or df_res.empty: return alertas
    
    # Filtro estricto por fechas
    f_ini_dt = pd.to_datetime(f_ini)
    f_fin_dt = pd.to_datetime(f_fin)
    df_actual = df_res[(df_res['Fecha_Raw'] >= f_ini_dt) & (df_res['Fecha_Raw'] <= f_fin_dt)]
    
    grupos_n = ["Grupo 1", "Grupo 2", "Grupo 3", "Grupo 4"]
    for g in grupos_n:
        h = df_actual[df_actual["Grupo"] == g].sort_values("Fecha_Raw").to_dict('records')
        for i in range(1, len(h)):
            if not es_cambio_saludable(h[i-1]['Turno'], h[i]['Turno']):
                alertas.append({
                    "msg": f"⚠️ {g}: Salto Prohibido {h[i-1]['Turno']} -> {h[i]['Turno']}", 
                    "grupo": g, "f": h[i]['Fecha_Col']
                })
    return alertas
