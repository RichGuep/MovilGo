import streamlit as st


def pantalla_tecnicos():
    st.title("👷 Programador Técnicos")
    st.success("Módulo técnicos funcionando")


def pantalla_abordaje():
    st.title("🚍 Programador Personal Abordaje")
    st.success("Módulo abordaje funcionando")


def pantalla_programador():

    modulo = st.radio(
        "Selecciona módulo",
        [
            "👷 Técnicos",
            "🚍 Personal Abordaje"
        ],
        horizontal=True
    )

    if modulo == "👷 Técnicos":
        pantalla_tecnicos()
    else:
        pantalla_abordaje()
