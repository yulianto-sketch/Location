import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
from datetime import datetime

# Konfigurasi Halaman
st.set_page_config(page_title="Peta Turing Privat", layout="wide")
st.title("📍 Live Tracking Lokasi Grup Turing")

# --- 1. DATABASE SQLITE ---
def init_db():
    conn = sqlite3.connect('turing_lokasi.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anggota (
            nama TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            waktu TEXT
        )
    ''')
    conn.commit()
    return conn

conn = init_db()

# --- 2. SESSION STATE ---
if "nama_saya" not in st.session_state:
    st.session_state.nama_saya = ""
if "sedang_gabung" not in st.session_state:
    st.session_state.sedang_gabung = False

# --- SIDEBAR: KONTROL SESI ---
st.sidebar.header("⚙️ Sesi Turing")

if not st.session_state.sedang_gabung:
    st.sidebar.info("Masukkan nama Anda untuk bergabung ke dalam peta grup.")
    input_nama = st.sidebar.text_input("Nama Anda / Panggilan:")
    
    # Input Koordinat (Akan diisi otomatis oleh tombol GPS di bawah)
    col1, col2 = st.sidebar.columns(2)
    with col1:
        my_lat = st.sidebar.number_input("Latitude", value=0.0, format="%.6f", key="init_lat")
    with col2:
        my_lon = st.sidebar.number_input("Longitude", value=0.0, format="%.6f", key="init_lon")
        
    if st.sidebar.button("🚀 Gabung Sesi Turing", type="primary"):
        if input_nama.strip() != "":
            if my_lat == 0.0 and my_lon == 0.0:
                st.sidebar.error("Klik tombol 'Dapatkan Lokasi Saya (GPS)' di layar utama dulu agar koordinat asli HP terdeteksi!")
            else:
                st.session_state.nama_saya = input_nama.strip()
                st.session_state.sedang_gabung = True
                
                waktu_sekarang = datetime.now().strftime("%H:%M:%S")
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO anggota (nama, lat, lon, waktu)
                    VALUES (?, ?, ?, ?)
                ''', (st.session_state.nama_saya, my_lat, my_lon, waktu_sekarang))
                conn.commit()
                st.rerun()
        else:
            st.sidebar.error("Nama tidak boleh kosong!")

else:
    st.sidebar.success(f"Aktif sebagai: **{st.session_state.nama_saya}**")
    
    # TOMBOL KELUAR SESI (HANYA MENGHAPUS DIRI SENDIRI)
    if st.sidebar.button("🚪 Keluar Sesi", type="secondary"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota WHERE nama = ?", (st.session_state.nama_saya,))
        conn.commit()
        
        st.session_state.sedang_gabung = False
        st.session_state.nama_saya = ""
        st.rerun()

# --- 3. KOMPONEN GET GPS (HTML5 GEOLOCATION REAL) ---
st.subheader("📡 Deteksi Lokasi Asli HP / GPS")

# Script untuk mengambil GPS browser secara akurat
html_get_gps = """
<div style="background-color: #f0f2f6; padding: 10px; border-radius: 8px;">
    <button onclick="getLocation()" style="padding: 8px 16px; background-color: #ff4b4b; color: white; border: none; border-radius: 4px; cursor: pointer; font-weight: bold;">
        🎯 Ambil Lokasi GPS HP Saya Saat Ini
    </button>
    <p id="status_gps" style="margin-top: 8px; font-size: 14px; color: #333;"></p>
</div>

<script>
function getLocation() {
    const status = document.getElementById('status_gps');
    if (navigator.geolocation) {
        status.innerHTML = "Sedang mencari sinyal GPS...";
        navigator.geolocation.getCurrentPosition(showPosition, showError, {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        });
    } else {
        status.innerHTML = "Browser Anda tidak mendukung Geolocation GPS.";
    }
}

function showPosition(position) {
    const lat = position.coords.latitude;
    const lng = position.coords.longitude;
    const status = document.getElementById('status_gps');
    status.innerHTML = "<b>Lokasi GPS Berhasil Didapat!</b><br>Latitude: " + lat + "<br>Longitude: " + lng + "<br><i>Silakan salin/masukkan nilai ini ke kolom atau tekan tombol kirim.</i>";
}

function showError(error) {
    const status = document.getElementById('status_gps');
    switch(error.code) {
        case error.PERMISSION_DENIED:
            status.innerHTML = "<b>Akses GPS Ditolak!</b> Harap izinkan akses lokasi (Location Access) di pengaturan browser HP Anda.";
            break;
        case error.POSITION_UNAVAILABLE:
            status.innerHTML = "Informasi lokasi tidak tersedia.";
            break;
        case error.TIMEOUT:
            status.innerHTML = "Waktu pencarian GPS habis.";
            break;
        default:
            status.innerHTML = "Terjadi kesalahan mengambil GPS.";
            break;
    }
}
</script>
"""

st.components.v1.html(html_get_gps, height=130)

# Update lokasi berkala jika sudah bergabung
if st.session_state.sedang_gabung:
    st.markdown("---")
    col_u1, col_u2, col_u3 = st.columns([2, 2, 2])
    with col_u1:
        cur_lat = st.number_input("Latitude Baru", value=0.0, format="%.6f", key="update_lat")
    with col_u2:
        cur_lon = st.number_input("Longitude Baru", value=0.0, format="%.6f", key="update_lon")
    with col_u3:
        st.write("")
        st.write("")
        if st.button("📍 Update Posisi Saya"):
            if cur_lat != 0.0 and cur_lon != 0.0:
                waktu_sekarang = datetime.now().strftime("%H:%M:%S")
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE anggota SET lat = ?, lon = ?, waktu = ? WHERE nama = ?
                ''', (cur_lat, cur_lon, waktu_sekarang, st.session_state.nama_saya))
                conn.commit()
                st.success("Posisi berhasil diperbarui!")
                st.rerun()

st.markdown("---")

# --- 4. TAMPILAN PETA BERSAMA (SATU LAYAR UNTUK SEMUA) ---
st.subheader("🗺️ Peta Pantauan Anggota Turing Aktif")

df_turing = pd.read_sql("SELECT * FROM anggota", conn)

if not df_turing.empty:
    st.write(f"Total anggota aktif saat ini: **{len(df_turing)} orang**")
    
    # Hitung titik tengah berdasarkan rata-rata lokasi anggota
    center_lat = df_turing['lat'].mean()
    center_lon = df_turing['lon'].mean()
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    for idx, row in df_turing.iterrows():
        is_me = (st.session_state.sedang_gabung and row['nama'].lower() == st.session_state.nama_saya.lower())
        
        warna_marker = 'red' if is_me else 'blue'
        ikon_simbol = 'user' if is_me else 'motorcycle'
        
        popup_html = f"<b>{row['nama']}</b> {'(Anda)' if is_me else ''}<br><small>Update: {row['waktu']}</small>"
        
        folium.Marker(
            [row['lat'], row['lon']], 
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=row['nama'],
            icon=folium.Icon(color=warna_marker, icon=ikon_simbol, prefix='fa')
        ).add_to(m)

    st_folium(m, width=1100, height=500)
    
    if st.button("🔄 Refresh Peta"):
        st.rerun()
else:
    st.info("Belum ada anggota yang bergabung di peta.")
