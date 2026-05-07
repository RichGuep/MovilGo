import streamlit as st
import pandas as pd
import io
import holidays
from datetime import datetime, timedelta
from github import Github

# --- 1. CONFIGURACIÓN Y CONSTANTES VISUALES ---
URL_BASE = "https://raw.githubusercontent.com/RichGuep/movilgo/main/"
LOGO_APP = f"{URL_BASE}MovilGo.png"

# --- 2. CONEXIÓN Y PERSISTENCIA GITHUB ---

def conectar_github():
    try:
        if "GITHUB_TOKEN" not in st.secrets:
            st.error("❌ Token GITHUB_TOKEN no configurado en secrets.")
            return None
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except Exception as e:
        st.error(f"Error GitHub: {e}")
        return None

def obtener_ultimo_estado_github(repo):
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

def guardar_malla_en_historico(df_nueva):
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

# --- 3. LÓGICA DE SALUD Y FORMATO VISUAL ---

def es_cambio_saludable(ayer, hoy):
    if ayer in ["DESC", "COMP", "OFF"] or hoy in ["DESC", "COMP", "OFF"]: return True
    jerarquia = {"T1": 1, "T2": 2, "T3": 3}
    return jerarquia.get(hoy, 0) >= jerarquia.get(ayer, 0)

def color_t(val):
    """Diccionario de colores para los turnos"""
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

def aplicar_estilos(df):
    """Aplica los colores al DataFrame para Streamlit"""
    return df.style.applymap(color_t)

# --- 4. MOTOR DE GENERACIÓN ---

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
                "Fecha_Raw": fecha_dt, "Noches_Acum": n_a,
                "Deuda_Compensatorio": deudas[g]
            })
            mem_t[g] = t_f; mem_n[g] = n_a

    return pd.DataFrame(resultados)

def generar_malla_personas(df_malla, df_personal):
    """Cruce de grupos con nombres de personas"""
    if df_personal.empty:
        return pd.DataFrame()
    df_merged = pd.merge(df_personal, df_malla, on="Grupo")
    malla_pivote = df_merged.pivot(index=["Nombre", "Grupo"], columns="Fecha_Col", values="Turno")
    return malla_pivote

# --- 5. VALIDADOR ---

def validar_malla_saludable(df_res, f_ini, f_fin):
    alertas = []
    if df_res is None or df_res.empty: return alertas
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

# --- 6. INTERFAZ PRINCIPAL ---

def main():
    st.set_page_config(page_title="MovilGo Logic", layout="wide", page_icon="⚙️")
    
    # Sidebar
    st.sidebar.image(LOGO_APP, width=180)
    st.sidebar.title("Configuración")
    f_ini = st.sidebar.date_input("Fecha Inicio", datetime.now())
    f_fin = st.sidebar.date_input("Fecha Fin", datetime.now() + timedelta(days=14))
    
    repo = conectar_github()
    
    if st.sidebar.button("🚀 Generar y Visualizar"):
        if repo:
            # Generar datos
            df_res = generar_malla_base(f_ini, f_fin, repo)
            df_personal = cargar_excel("personal.xlsx")
            
            # Pestañas
            tab1, tab2, tab3 = st.tabs(["📊 Malla Grupos", "👤 Malla Personas", "🛡️ Salud Laboral"])
            
            with tab1:
                st.subheader("Distribución por Grupos")
                malla_g = df_res.pivot(index="Grupo", columns="Fecha_Col", values="Turno")
                st.dataframe(aplicar_estilos(malla_g), use_container_width=True)
                
            with tab2:
                st.subheader("Malla por Colaborador")
                if not df_personal.empty:
                    malla_p = generar_malla_personas(df_res, df_personal)
                    st.dataframe(aplicar_estilos(malla_p), use_container_width=True)
                else:
                    st.info("Sube 'personal.xlsx' a GitHub para ver nombres individuales.")
            
            with tab3:
                st.subheader("Análisis de Riesgos")
                alertas = validar_malla_saludable(df_res, f_ini, f_fin)
                if alertas:
                    for a in alertas: st.warning(f"{a['msg']} el {a['f']}")
                else:
                    st.success("✅ Turnos conformes a la normativa de salud.")

            # Opción de guardado
            st.divider()
            if st.button("💾 Guardar esta Malla en Histórico"):
                guardar_malla_en_historico(df_res)
        else:
            st.error("No se pudo conectar con el repositorio.")

if __name__ == "__main__":
    main()
