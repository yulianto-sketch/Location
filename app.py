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

# --- SIDEBAR: KONTROL SESI & DAFTAR ANGGOTA ---
st.sidebar.header("⚙️ Sesi Turing")

if not st.sidebar.get_option if hasattr(st.sidebar, 'get_option') else True:
    pass

if not st.session_state.sedang_gabung:
    st.sidebar.info("Masukkan nama kamu untuk bergabung ke dalam sesi turing.")
    input_nama = st.sidebar.text_input("Nama Kamu / Panggilan:")
    
    if st.sidebar.button("🚀 Gabung Sesi Turing", type="primary"):
        if input_nama.strip() != "":
            st.session_state.nama_saya = input_nama.strip()
            st.session_state.sedang_gabung = True
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

st.sidebar.markdown("---")

# --- 3. DAFTAR NAMA ANGGOTA YANG GABUNG DI SIDEBAR ---
st.sidebar.subheader("📋 Anggota Aktif di Grup")
df_sidebar = pd.read_sql("SELECT nama, waktu FROM anggota", conn)
if not df_sidebar.empty:
    st.sidebar.write(f"Total: **{len(df_sidebar)} orang** online")
    for idx, row in df_sidebar.iterrows():
        status_kamu = " (Kamu)" if row['nama'] == st.session_state.nama_saya else ""
        st.sidebar.markdown(f"- 🏍️ **{row['nama']}**{status_kamu} <br><small style='color:gray;'>Update: {row['waktu']}</small>", unsafe_allow_html=True)
else:
    st.sidebar.info("Belum ada anggota yang bergabung.")

# --- 4. PROSES LOKASI GPS (BACKGROUND SILENT UPDATE) ---
if st.session_state.sedang_gabung:
    # Tangkap parameter latitude & longitude dari URL Query
    query_params = st.query_params
    if "lat" in query_params and "lon" in query_params:
        try:
            lat_val = float(query_params["lat"])
            lon_val = float(query_params["lon"])
            waktu_sekarang = datetime.now().strftime("%H:%M:%S")
            
            # Simpan/Update otomatis ke Database SQLite
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO anggota (nama, lat, lon, waktu)
                VALUES (?, ?, ?, ?)
            ''', (st.session_state.nama_saya, lat_val, lon_val, waktu_sekarang))
            conn.commit()
        except ValueError:
            pass

    # Script JS untuk deteksi GPS tanpa mengganggu tampilan utama
    html_gps_script = """
    <div id="status_gps" style="padding: 10px 14px; background-color: #e8f4f8; border-radius: 8px; font-family: sans-serif; font-size: 14px; border-left: 4px solid #0288d1; margin-bottom: 10px;">
        📡 GPS Aktif: Mengambil sinyal lokasi akurat dari HP kamu...
    </div>

    <script>
    function trackGPS() {
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                function(position) {
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    
                    document.getElementById('status_gps').innerHTML = "✅ <b>GPS Terkoneksi:</b> Lat: " + lat.toFixed(5) + " | Lon: " + lon.toFixed(5);
                    
                    // Kirim koordinat ke URL secara senyap (silent update) setiap 30 detik
                    const currentUrl = new URL(window.parent.location.href);
                    if (currentUrl.searchParams.get("lat") != lat || currentUrl.searchParams.get("lon") != lon) {
                        currentUrl.searchParams.set("lat", lat);
                        currentUrl.searchParams.set("lon", lon);
                        window.parent.history.replaceState({}, '', currentUrl.href);
                    }
                },
                function(error) {
                    document.getElementById('status_gps').innerHTML = "⚠️ <b>GPS Gagal:</b> Pastikan izin lokasi (Location Permission) di HP/Browser sudah di-ALLOW (Diizinkan).";
                },
                { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
            );
        }
    }

    // Jalankan pertama kali dan ulangi setiap 30 detik otomatis di background
    trackGPS();
    setInterval(trackGPS, 30000);
    </script>
    """
    st.components.v1.html(html_gps_script, height=60)

st.markdown("---")

# --- 5. TAMPILAN PETA BERSAMA (SATU LAYAR UNTUK SEMUA) ---
col_tittle, col_btn = st.columns([3, 1])
with col_tittle:
    st.subheader("🗺️ Peta Pantauan Anggota Turing Aktif")
with col_btn:
    st.write("")
    if st.button("🔄 Refresh Peta Manual"):
        st.rerun()

df_turing = pd.read_sql("SELECT * FROM anggota", conn)

if not df_turing.empty:
    st.caption(f"Semua titik lokasi anggota disatukan dalam 1 layar peta.")
    
    # Hitung titik tengah peta berdasarkan rata-rata posisi anggota
    center_lat = df_turing['lat'].mean()
    center_lon = df_turing['lon'].mean()
    
    if pd.isna(center_lat) or pd.isna(center_lon) or (center_lat == 0 and center_lon == 0):
        center_lat, center_lon = -6.2088, 106.8456
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    for idx, row in df_turing.iterrows():
        if row['lat'] == 0.0 and row['lon'] == 0.0:
            continue
            
        is_me = (st.session_state.sedang_gabung and row['nama'].lower() == st.session_state.nama_saya.lower())
        
        warna_marker = 'red' if is_me else 'blue'
        ikon_simbol = 'user' if is_me else 'motorcycle'
        
        popup_html = f"<b>{row['nama']}</b> {'(Kamu)' if is_me else ''}<br><small>Update: {row['waktu']}</small>"
        
        folium.Marker(
            [row['lat'], row['lon']], 
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=row['nama'],
            icon=folium.Icon(color=warna_marker, icon=ikon_simbol, prefix='fa')
        ).add_to(m)

        # Lingkaran area di sekitar marker
        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=100,
            color='red' if is_me else 'blue',
            fill=True,
            fill_opacity=0.15
        ).add_to(m)

    # Render peta stabil tanpa kedip
    st_folium(m, width=1100, height=520)

else:
    st.info("Belum ada anggota yang bergabung di sesi turing. Masukkan nama kamu di sidebar untuk mulai membagikan lokasi dan melihat peta.")
