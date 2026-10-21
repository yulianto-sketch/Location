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

# --- 3. AUTO GPS SENDER (HTML/JS INTEGRATION) ---
if st.session_state.sedang_gabung:
    st.subheader(f"📡 Status Lokasi Live: {st.session_state.nama_saya}")
    
    # Komponen JS yang otomatis mengambil koordinat HP & update ke query params / session
    html_autogps = f"""
    <div id="status" style="padding: 12px; background-color: #e8f4f8; border-radius: 8px; font-family: sans-serif; border-left: 4px solid #0288d1;">
        ⏳ Menghubungkan ke GPS HP...
    </div>

    <script>
    function sendLocation() {{
        const statusDiv = document.getElementById('status');
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    
                    statusDiv.innerHTML = "<b>✅ GPS Terhubung Akurat!</b><br>Latitude: " + lat + "<br>Longitude: " + lon;
                    
                    // Mengirim data ke URL param untuk ditangkap Streamlit
                    const url = new URL(window.parent.location.href);
                    if (url.searchParams.get("lat") != lat || url.searchParams.get("lon") != lon) {{
                        url.searchParams.set("lat", lat);
                        url.searchParams.set("lon", lon);
                        window.parent.location.href = url.href;
                    }}
                }},
                function(error) {{
                    switch(error.code) {{
                        case error.PERMISSION_DENIED:
                            statusDiv.innerHTML = "❌ <b>Akses GPS Ditolak!</b> Mohon aktifkan izin lokasi di browser HP kamu.";
                            break;
                        default:
                            statusDiv.innerHTML = "⚠️ Gagal mengambil sinyal GPS. Pastikan Lokasi/GPS HP aktif.";
                    }}
                }},
                {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
            );
        }} else {{
            statusDiv.innerHTML = "❌ Browser tidak mendukung Geolocation.";
        }}
    }}

    // Jalankan otomatis begitu komponen dimuat
    sendLocation();
    </script>
    """
    st.components.v1.html(html_autogps, height=90)

    # Tangkap data GPS otomatis dari URL Query Parameters
    query_params = st.query_params
    if "lat" in query_params and "lon" in query_params:
        try:
            auto_lat = float(query_params["lat"])
            auto_lon = float(query_params["lon"])
            waktu_sekarang = datetime.now().strftime("%H:%M:%S")
            
            # Simpan/Update otomatis ke Database SQLite
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO anggota (nama, lat, lon, waktu)
                VALUES (?, ?, ?, ?)
            ''', (st.session_state.nama_saya, auto_lat, auto_lon, waktu_sekarang))
            conn.commit()
        except ValueError:
            pass

    col_btn1, col_btn2 = st.columns([1, 4])
    with col_btn1:
        if st.button("🔄 Update Posisi HP Saya"):
            st.rerun()

st.markdown("---")

# --- 4. PETA BERSAMA (SATU LAYAR UNTUK SEMUA ANGGOTA) ---
st.subheader("🗺️ Peta Pantauan Anggota Turing Aktif")

df_turing = pd.read_sql("SELECT * FROM anggota", conn)

if not df_turing.empty:
    st.write(f"Total anggota terpantau aktif: **{len(df_turing)} orang**")
    
    # Hitung titik tengah berdasarkan seluruh lokasi anggota yang ada
    center_lat = df_turing['lat'].mean()
    center_lon = df_turing['lon'].mean()
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    for idx, row in df_turing.iterrows():
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

        # Lingkaran halus di sekitar titik
        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=100,
            color='red' if is_me else 'blue',
            fill=True,
            fill_opacity=0.1
        ).add_to(m)

    st_folium(m, width=1100, height=500)
else:
    st.info("Belum ada anggota yang bergabung. Masukkan nama kamu di sidebar untuk mulai membagikan lokasi.")
