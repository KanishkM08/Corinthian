import streamlit as st


st.title("Corinthian")

file  = st.file_uploader("Upload your media file", type=["jpg", "jpeg", "png", "mp4", "heic", "mov", "avi"])

if file:
    st.success("Success")