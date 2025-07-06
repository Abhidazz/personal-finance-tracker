# config.py
import streamlit as st

MONGO_URI = st.secrets["MONGO_URI"]
DB_NAME = st.secrets["DB_NAME"]
print("Mongo URI loaded:", MONGO_URI)