import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
from datetime import datetime
import time

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
if "my_lat" not in st.session_state:
    st.session_state.my_lat = 0.0
if "my_lon" not in st.session_state:
    st.session_state.my_lon = 0.0

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
        st.session_state.my_lat = 0.0
        st.session_state.my_lon = 0.0
        st.rerun()

# --- 3. PROSES LOKASI GPS & AUTO-UPDATE 1 MENIT ---
if st.session_state.sedang_gabung:
    st.subheader(f"📡 Status Lokasi Live: {st.session_state.nama_saya}")
    
    # Tangkap parameter latitude & longitude dari Query Params
    query_params = st.query_params
    if "lat" in query_params and "lon" in query_params:
        try:
            st.session_state.my_lat = float(query_params["lat"])
            st.session_state.my_lon = float(query_params["lon"])
            
            waktu_sekarang = datetime.now().strftime("%H:%M:%S")
            
            # Simpan/Update otomatis ke Database SQLite
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO anggota (nama, lat, lon, waktu)
                VALUES (?, ?, ?, ?)
            ''', (st.session_state.nama_saya, st.session_state.my_lat, st.session_state.my_lon, waktu_sekarang))
            conn.commit()
        except ValueError:
            pass

    # Komponen JS Geolocation + Timer Auto-Refresh 60 Detik (1 Menit)
    html_gps_script = f"""
    <div id="status_box" style="padding: 10px; background-color: #e8f4f8; border-radius: 8px; font-family: sans-serif; border-left: 4px solid #0288d1;">
        ⏳ Menghubungkan ke GPS HP...
    </div>

    <script>
    function updateGPS() {{
        const statusBox = document.getElementById('status_box');
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    
                    statusBox.innerHTML = "<b>✅ GPS Terkoneksi Presisi!</b><br>Lat: " + lat + " | Lon: " + lon + "<br><i>Auto-update ulang dalam 60 detik...</i>";
                    
                    // Mengirimkan parameter lokasi ke URL tanpa me-reload paksa iframe
                    const currentUrl = new URL(window.parent.location.href);
                    if (currentUrl.searchParams.get("lat") != lat || currentUrl.searchParams.get("lon") != lon) {{
                        currentUrl.searchParams.set("lat", lat);
                        currentUrl.searchParams.set("lon", lon);
                        window.parent.history.replaceState({{}}, '', currentUrl.href);
                    }}
                }},
                function(error) {{
                    statusBox.innerHTML = "⚠️ Gagal mengambil GPS. Pastikan izin lokasi/GPS di HP sudah di-ALLOW (Diizinkan).";
                }},
                {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
            );
        }} else {{
            statusBox.innerHTML = "❌ Browser tidak mendukung Geolocation.";
        }}
    }}

    // Jalankan pertama kali
    updateGPS();
    </script>
    """
    st.components.v1.html(html_gps_script, height=100)

st.markdown("---")

# --- 4. TAMPILAN PETA BERSAMA (SATU LAYAR UNTUK SEMUA) ---
st.subheader("🗺️ Peta Pantauan Anggota Turing Aktif")

df_turing = pd.read_sql("SELECT * FROM anggota", conn)

if not df_turing.empty:
    st.write(f"Total anggota aktif di peta: **{len(df_turing)} orang**")
    
    # Hitung titik tengah peta
    center_lat = df_turing['lat'].mean()
    center_lon = df_turing['lon'].mean()
    
    # Jika koordinat masih 0, default ke lokasi acuan sementara
    if center_lat == 0 or center_lon == 0:
        center_lat, center_lon = -6.2088, 106.8456
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=14)
    
    for idx, row in df_turing.iterrows():
        # Jangan tampilkan jika koordinat bernilai 0.0 (belum dapat GPS)
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

        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=80,
            color='red' if is_me else 'blue',
            fill=True,
            fill_opacity=0.15
        ).add_to(m)

    # Tampilkan Peta Folium dengan key dinamis agar tidak blank
    st_folium(m, width=1100, height=500, key=f"map_{int(time.time() // 10)}")

else:
    st.info("Belum ada anggota yang bergabung. Masukkan nama kamu di sidebar untuk bergabung.")

# --- 5. AUTOMATIC LOOP REFRESH PER 1 MENIT (60 DETIK) ---
if st.session_state.sedang_gabung:
    time.sleep(60)  # Menunggu 60 detik (1 menit)
    st.rerun()      # Re-run skrip otomatis untuk memperbarui GPS dan peta bersama
