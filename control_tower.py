import streamlit as st
import pandas as pd

def dashboard_control(df):

    st.title("🚀 Control Tower Operacional")

    # KPI 1
    st.metric("Total Registros", len(df))

    # KPI 2
    st.metric("Turnos TR", len(df[df["Turno"] == "TR"]))

    # KPI 3
    st.metric("Descansos", len(df[df["Turno"] == "DESC"]))

    st.divider()

    # ROTACIÓN
    st.subheader("🔄 Rotación por Grupo")
    rot = df.groupby(["Grupo", "Turno"]).size().unstack(fill_value=0)
    st.bar_chart(rot)

    # EQUILIBRIO
    st.subheader("⚖️ Equilibrio TR")
    if "Persona_TR" in df.columns:
        balance = df[df["Turno"] == "TR"].groupby("Persona_TR").size()
        st.bar_chart(balance)

    # AUDITORIA SIMPLE
    st.subheader("🚨 Alertas")
    if df["Grupo"].isna().any():
        st.warning("Hay registros sin grupo asignado")
