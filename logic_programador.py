# =====================================================
# 📊 MALLA CON DÍA + COLORES (CORREGIDO)
# =====================================================
st.subheader("📊 Malla de turnos")

# 1. Asegurarnos de que el día esté en español y bien formateado
dias_traduccion = {
    'Monday': 'Lun', 'Tuesday': 'Mar', 'Wednesday': 'Mié', 
    'Thursday': 'Jue', 'Friday': 'Vie', 'Saturday': 'Sáb', 'Sunday': 'Dom'
}
df["Día_Nom"] = pd.to_datetime(df["Fecha"]).dt.day_name().map(dias_traduccion)

# 2. Crear el pivot
pivot = df.pivot(index="Grupo", columns=["Fecha", "Día_Nom"], values="Turno")

def color(val):
    return {
        "T1":"background:#D8F3DC;color:#1B4332;font-weight:bold",
        "T2":"background:#DCEBFF;color:#1D3557;font-weight:bold",
        "T3":"background:#EADCF8;color:#5A189A;font-weight:bold",
        "DESCANSO":"background:#FFD6D6;color:#9D0208;font-weight:bold",
        "COMPENSADO":"background:#FFF3BF;color:#7F5539;font-weight:bold"
    }.get(val,"")

# 3. Mostrar con el MultiIndex (esto pondrá la fecha arriba y el día abajo)
st.dataframe(pivot.style.map(color), use_container_width=True)
