import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
from datetime import datetime, timedelta, timezone

# Konfigurasi Halaman
st.set_page_config(page_title="Peta Turing Privat", layout="wide")
st.title("📍 Live Tracking Lokasi Grup Turing")

# --- 1. TENTUKAN ZONA WAKTU WIB (UTC+7) ---
WIB = timezone(timedelta(hours=7))

# --- 2. DATABASE SQLITE ---
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

# --- 3. SESSION STATE ---
if "nama_saya" not in st.session_state:
    st.session_state.nama_saya = ""
if "sedang_gabung" not in st.session_state:
    st.session_state.sedang_gabung = False

# --- 4. TANGKAP DATA GPS SILENT UPDATE DARI URL (BACKGROUND FETCH) ---
query_params = st.query_params
if "lat" in query_params and "lon" in query_params and "user" in query_params:
    try:
        u_name = query_params["user"]
        u_lat = float(query_params["lat"])
        u_lon = float(query_params["lon"])
        
        # Waktu lokal WIB
        waktu_sekarang = datetime.now(WIB).strftime("%H:%M:%S")
        
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO anggota (nama, lat, lon, waktu)
            VALUES (?, ?, ?, ?)
        ''', (u_name, u_lat, u_lon, waktu_sekarang))
        conn.commit()
    except ValueError:
        pass

# --- 5. CEK APAKAH USER ADALAH ORANG PERTAMA YANG GABUNG ---
df_check = pd.read_sql("SELECT nama FROM anggota ORDER BY ROWID ASC LIMIT 1", conn)
is_first_member = False
if not df_check.empty:
    first_name = df_check.iloc[0]['nama']
    if st.session_state.sedang_gabung and st.session_state.nama_saya == first_name:
        is_first_member = True

# --- SIDEBAR: KONTROL SESI & KELUAR SESI ---
st.sidebar.header("⚙️ Sesi Turing")

if not st.session_state.sedang_gabung:
    # --- FORM LOGIN ---
    st.sidebar.info("Masukkan nama kamu untuk bergabung ke dalam sesi turing.")
    input_nama = st.sidebar.text_input("Nama Kamu / Panggilan:", key="input_nama_field")
    
    if st.sidebar.button("🚀 Gabung Sesi Turing", type="primary"):
        if input_nama.strip() != "":
            st.session_state.nama_saya = input_nama.strip()
            st.session_state.sedang_gabung = True
            
            # Catat langsung ke DB saat pertama kali gabung dengan waktu WIB
            waktu_sekarang = datetime.now(WIB).strftime("%H:%M:%S")
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR IGNORE INTO anggota (nama, lat, lon, waktu)
                VALUES (?, ?, ?, ?)
            ''', (st.session_state.nama_saya, -6.2088, 106.8456, waktu_sekarang))
            conn.commit()
            st.rerun()
        else:
            st.sidebar.error("Nama tidak boleh kosong!")

else:
    # --- MENU KETIKA SUDAH GABUNG ---
    st.sidebar.success(f"Aktif sebagai: **{st.session_state.nama_saya}**")
    st.sidebar.caption("📡 GPS aktif di latar belakang (update otomatis tiap 1 menit, hemat kuota).")
    
    st.sidebar.markdown("---")
    
    # TOMBOL KELUAR SESI UNTUK PRIBADI
    if st.sidebar.button("🚪 Keluar Sesi", type="secondary"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota WHERE nama = ?", (st.session_state.nama_saya,))
        conn.commit()
        
        st.session_state.sedang_gabung = False
        st.session_state.nama_saya = ""
        st.rerun()

    # TOMBOL RESET KHUSUS ORANG PERTAMA YANG GABUNG
    if is_first_member:
        st.sidebar.markdown("---")
        st.sidebar.warning("⭐ Anda adalah pembuat/peserta pertama sesi ini.")
        if st.sidebar.button("🗑️ Reset Semua Anggota (Akhiri Sesi)", type="primary"):
            cursor = conn.cursor()
            cursor.execute("DELETE FROM anggota")
            conn.commit()
            
            st.session_state.sedang_gabung = False
            st.session_state.nama_saya = ""
            st.success("Sesi di-reset untuk semua orang.")
            st.rerun()

st.sidebar.markdown("---")

# --- 6. DAFTAR NAMA ANGGOTA AKTIF DI SIDEBAR (FORMAT RAPI & WIB) ---
st.sidebar.subheader("📋 Anggota Aktif di Grup")
df_sidebar = pd.read_sql("SELECT nama, waktu FROM anggota", conn)
if not df_sidebar.empty:
    st.sidebar.write(f"Total: **{len(df_sidebar)} orang** online")
    for idx, row in df_sidebar.iterrows():
        status_kamu = " (Kamu)" if row['nama'] == st.session_state.nama_saya else ""
        # Tampilan daftar nama dan waktu update WIB yang lebih rapi
        st.sidebar.markdown(f"🏍️ **{row['nama']}**{status_kamu}<br><small style='color:gray;'>🕒 Update (WIB): {row['waktu']}</small>", unsafe_allow_html=True)
        st.sidebar.markdown("---")
else:
    st.sidebar.info("Belum ada anggota yang bergabung.")

# --- 7. SKRIP JAVASCRIPT SILENT GPS BACKGROUND (1 MENIT SEKALI) ---
if st.session_state.sedang_gabung:
    current_user_name = st.session_state.nama_saya
    
    html_silent_gps = f"""
    <div style="padding: 10px; background-color: #e8f4f8; border-radius: 6px; font-family: sans-serif; font-size: 13px; border-left: 4px solid #0288d1; margin-bottom: 10px;">
        📡 <b>Background Tracker Aktif:</b> Mengirim update posisi WIB tiap 1 menit secara senyap.
    </div>

    <script>
    const userName = "{current_user_name}";

    function sendSilentGPS() {{
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    
                    const currentUrl = new URL(window.parent.location.href);
                    currentUrl.searchParams.set("user", userName);
                    currentUrl.searchParams.set("lat", lat);
                    currentUrl.searchParams.set("lon", lon);
                    window.parent.history.replaceState({{}}, '', currentUrl.href);
                }},
                function(error) {{
                    console.log("GPS Error: " + error.message);
                }},
                {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
            );
        }}
    }}

    sendSilentGPS();
    setInterval(sendSilentGPS, 60000);
    </script>
    """
    st.components.v1.html(html_silent_gps, height=50)

# --- 8. TAMPILAN PETA BERSAMA (STABIL 1 LAYAR) ---
col_tittle, col_btn = st.columns([3, 1])
with col_tittle:
    st.subheader("🗺️ Peta Pantauan Anggota Turing Aktif")
with col_btn:
    st.write("")
    if st.button("🔄 Refresh Peta Manual"):
        st.rerun()

df_turing = pd.read_sql("SELECT * FROM anggota", conn)

if not df_turing.empty:
    center_lat = df_turing['lat'].mean()
    center_lon = df_turing['lon'].mean()
    
    if pd.isna(center_lat) or pd.isna(center_lon) or (center_lat == 0 and center_lon == 0):
        center_lat, center_lon = -6.2088, 106.8456
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    for idx, row in df_turing.iterrows():
        if row['lat'] is None or row['lon'] is None or (row['lat'] == 0.0 and row['lon'] == 0.0):
            continue
            
        is_me = (st.session_state.sedang_gabung and row['nama'].lower() == st.session_state.nama_saya.lower())
        
        warna_marker = 'red' if is_me else 'blue'
        ikon_simbol = 'user' if is_me else 'motorcycle'
        
        popup_html = f"<b>{row['nama']}</b> {'(Kamu)' if is_me else ''}<br><small>Update (WIB): {row['waktu']}</small>"
        
        folium.Marker(
            [row['lat'], row['lon']], 
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=row['nama'],
            icon=folium.Icon(color=warna_marker, icon=ikon_simbol, prefix='fa')
        ).add_to(m)

        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=100,
            color='red' if is_me else 'blue',
            fill=True,
            fill_opacity=0.15
        ).add_to(m)

    st_folium(m, width=1100, height=520)

else:
    st.info("Belum ada anggota yang bergabung di sesi turing. Masukkan nama kamu di sidebar untuk mulai.")
