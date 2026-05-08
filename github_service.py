import streamlit as st
from github import Github

def get_repo():
    try:
        g = Github(st.secrets["GITHUB_TOKEN"])
        return g.get_repo("RichGuep/movilgo")
    except:
        return None
