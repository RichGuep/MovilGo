import streamlit as st
from logic.programador import generar_malla
from dashboard.control_tower import dashboard_control

st.set_page_config(page_title="MovilGo Enterprise", layout="wide")

st.title("🚀 MovilGo Enterprise")

menu = st.sidebar.radio(
    "Navegación",
    ["📅 Programación", "📊 Control Tower"]
)

if menu == "📅 Programación":

    st.subheader("Generador de Malla")

    if st.button("Generar"):

        df = generar_malla(
            fecha_ini=st.date_input("Inicio"),
            fecha_fin=st.date_input("Fin"),
            grupos=["A","B","C","D","E"],
            personal_grupos={"A":["Juan"],"B":["Pedro"]},
            descansos={"A":0,"B":2,"C":4,"D":5,"E":6}
        )

        st.session_state["df"] = df
        st.success("Malla generada")

    if "df" in st.session_state:
        st.dataframe(st.session_state["df"])

if menu == "📊 Control Tower":

    if "df" in st.session_state:
        dashboard_control(st.session_state["df"])
    else:
        st.warning("Genera primero la malla")
