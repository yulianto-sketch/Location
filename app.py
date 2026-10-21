import streamlit as st  # <-- Sudah diperbaiki di sini (menggunakan st)
import pandas as pd
import folium
from streamlit_folium import st_folium
import time

st.set_page_config(page_title="Peta Turing Privat", layout="wide")
st.title("📍 Pelacak Lokasi Grup Turing")

# 1. Input Nama User
nama_user = st.text_input("Masukkan Nama Kamu untuk Gabung:", key="username")

html_gps = """
<script>
navigator.geolocation.getCurrentPosition(success, error);
function success(position) {
    const lat = position.coords.latitude;
    const lng = position.coords.longitude;
    // Kirim data koordinat ke Streamlit
    window.parent.postMessage({type: 'streamlit:setComponentValue', value: {lat: lat, lng: lng}}, '*');
}
function error() {
    console.log("Akses GPS ditolak.");
}
</script>
"""

if nama_user:
    st.components.v1.html(html_gps, height=0)
    
    st.success(f"Halo {nama_user}, lokasimu sedang diperbarui otomatis...")
    
    # 2. Menampilkan Peta Bersama
    st.subheader("Peta Posisi Anggota")
    
    # Contoh titik koordinat default (Jakarta)
    data_turing = pd.DataFrame({
        'Nama': ['Kamu', 'Teman 1'],
        'lat': [-6.2088, -6.2100],
        'lon': [106.8456, 106.8500]
    })
    
    m = folium.Map(location=[data_turing['lat'].mean(), data_turing['lon'].mean()], zoom_start=14)
    
    for idx, row in data_turing.iterrows():
        folium.Marker(
            [row['lat'], row['lon']], 
            popup=row['Nama'],
            tooltip=row['Nama'],
            icon=folium.Icon(color='red' if row['Nama'] == 'Kamu' else 'blue', icon='info-sign')
        ).add_to(m)
        
    st_folium(m, width=700, height=500)
    
    # Fitur auto-refresh per 60 detik (1 menit)
    time.sleep(60)
    st.rerun()
else:
    st.info("Silakan masukkan namamu terlebih dahulu untuk membagikan lokasi dan melihat peta.")
