import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3

# Konfigurasi Halaman
st.set_page_config(page_title="Peta Turing Privat", layout="wide")
st.title("📍 Live Tracking Lokasi Grup Turing")

# --- 1. DATABASE SQLITE & MIGRASI SKEMA OTOMATIS ---
def init_db():
    conn = sqlite3.connect('turing_lokasi.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anggota (
            nama TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            waktu TEXT,
            status_aktif INTEGER DEFAULT 1
        )
    ''')
    # Pastikan kolom status_aktif tetap ada jika database lama sudah terlanjur dibuat
    try:
        cursor.execute("ALTER TABLE anggota ADD COLUMN status_aktif INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass # Kolom sudah ada, abaikan error
    conn.commit()
    return conn

conn = init_db()

# --- 2. SESSION STATE ---
if "nama_saya" not in st.session_state:
    st.session_state.nama_saya = ""

# --- 3. CEK INTEGRITAS SESI (LOGOUT OTOMATIS JIKA DI-RESET ADMIN) ---
if st.session_state.nama_saya != "":
    cursor = conn.cursor()
    cursor.execute("SELECT nama FROM anggota WHERE nama = ? AND status_aktif = 1", (st.session_state.nama_saya,))
    active_user = cursor.fetchone()
    if not active_user:
        # Jika sudah di-reset admin atau dihapus, bersihkan session lokal
        st.session_state.nama_saya = ""

# --- 4. TANGKAP DATA GPS & WAKTU LOKAL WIB DARI BROWSER ---
query_params = st.query_params
if "lat" in query_params and "lon" in query_params and "user" in query_params and "time" in query_params:
    try:
        u_name = query_params["user"]
        u_lat = float(query_params["lat"])
        u_lon = float(query_params["lon"])
        waktu_sekarang = query_params["time"]
        
        cursor = conn.cursor()
        cursor.execute("SELECT status_aktif FROM anggota WHERE nama = ?", (u_name,))
        res = cursor.fetchone()
        
        if res and res[0] == 1:
            cursor.execute('''
                UPDATE anggota SET lat = ?, lon = ?, waktu = ? WHERE nama = ?
            ''', (u_lat, u_lon, waktu_sekarang, u_name))
            conn.commit()
    except ValueError:
        pass

# --- SIDEBAR: KONTROL SESI ---
st.sidebar.header("⚙️ Sesi Lokasi")

# JIKA BELUM LOGIN / BELUM ADA NAMA
if st.session_state.nama_saya == "":
    st.sidebar.info("Silakan masukkan nama kamu untuk bergabung ke dalam sesi lokasi.")
    input_nama = st.sidebar.text_input("Nama Kamu / Panggilan:", key="input_nama_field")
    
    if st.sidebar.button("🚀 Gabung Sesi Lokasi", type="primary"):
        if input_nama.strip() != "":
            clean_name = input_nama.strip()
            
            cursor = conn.cursor()
            cursor.execute("SELECT nama FROM anggota WHERE nama = ?", (clean_name,))
            existing = cursor.fetchone()
            
            if existing:
                st.sidebar.error("❌ Nama tersebut sudah digunakan oleh peserta lain. Gunakan nama panggilan lain.")
            else:
                st.session_state.nama_saya = clean_name
                cursor.execute('''
                    INSERT OR REPLACE INTO anggota (nama, lat, lon, waktu, status_aktif)
                    VALUES (?, ?, ?, ?, ?)
                ''', (clean_name, -6.2088, 106.8456, "Baru Bergabung", 1))
                conn.commit()
                st.rerun()
        else:
            st.sidebar.error("Nama tidak boleh kosong!")

    st.info("👋 **Selamat datang!** Masukkan nama kamu di sidebar kiri untuk masuk ke peta grup lokasi.")

# JIKA SUDAH LOGIN (SESI TERSIMPAN MESKI KELUAR BROWSER)
else:
    st.sidebar.success(f"Aktif sebagai: **{st.session_state.nama_saya}**")
    st.sidebar.caption("📡 Sesi tersimpan. Meski browser ditutup, kamu tetap tercatat di grup sampai logout/reset.")
    
    # TOMBOL LOGOUT PRIBADI
    if st.sidebar.button("🚪 Logout / Keluar Sesi", type="primary"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota WHERE nama = ?", (st.session_state.nama_saya,))
        conn.commit()
        
        st.session_state.nama_saya = ""
        st.rerun()

    # PANEL RESET SEMUA ANGGOTA DENGAN KODE PIN 123
    st.sidebar.markdown("---")
    st.sidebar.write("🛠️ **Panel Reset Grup (Butuh Kode)**")
    pin_input = st.sidebar.text_input("Masukkan Kode Reset:", type="password", key="pin_reset_input")
    
    if st.sidebar.button("🗑️ Reset Semua Anggota", type="secondary"):
        if pin_input == "123":
            cursor = conn.cursor()
            cursor.execute("DELETE FROM anggota")
            conn.commit()
            
            st.session_state.nama_saya = ""
            st.success("Semua data sesi berhasil di-reset untuk semua orang!")
            st.rerun()
        else:
            st.sidebar.error("❌ Kode PIN salah! (Gunakan kode: 123)")

    st.sidebar.markdown("---")

    # --- DAFTAR ANGGOTA AKTIF ---
    st.sidebar.subheader("📋 Anggota Aktif di Grup")
    df_sidebar = pd.read_sql("SELECT nama, waktu FROM anggota WHERE status_aktif = 1", conn)
    if not df_sidebar.empty:
        st.sidebar.write(f"Total: **{len(df_sidebar)} orang** online")
        for idx, row in df_sidebar.iterrows():
            status_kamu = " (Kamu)" if row['nama'] == st.session_state.nama_saya else ""
            st.sidebar.markdown(f"🏍️ **{row['nama']}**{status_kamu}<br><small style='color:gray;'>🕒 Update (WIB): {row['waktu']}</small>", unsafe_allow_html=True)
            st.sidebar.markdown("---")
    else:
        st.sidebar.info("Belum ada anggota lain yang bergabung.")

    # --- SKRIP JAVASCRIPT SILENT GPS ---
    current_user_name = st.session_state.nama_saya
    
    html_silent_gps = f"""
    <div style="padding: 10px; background-color: #e8f4f8; border-radius: 6px; font-family: sans-serif; font-size: 13px; border-left: 4px solid #0288d1; margin-bottom: 10px;">
        📡 <b>Background Tracker Aktif:</b> Mengirim posisi & jam WIB tiap 1 menit secara senyap.
    </div>

    <script>
    const userName = "{current_user_name}";

    function sendSilentGPS() {{
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    
                    const now = new Date();
                    const hours = String(now.getHours()).padStart(2, '0');
                    const minutes = String(now.getMinutes()).padStart(2, '0');
                    const seconds = String(now.getSeconds()).padStart(2, '0');
                    const timeWIB = hours + ":" + minutes + ":" + seconds;
                    
                    const currentUrl = new URL(window.parent.location.href);
                    currentUrl.searchParams.set("user", userName);
                    currentUrl.searchParams.set("lat", lat);
                    currentUrl.searchParams.set("lon", lon);
                    currentUrl.searchParams.set("time", timeWIB);
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

    # --- TAMPILAN PETA BERSAMA ---
    col_tittle, col_btn = st.columns([3, 1])
    with col_tittle:
        st.subheader("🗺️ Peta Pantauan Anggota Aktif")
    with col_btn:
        st.write("")
        if st.button("🔄 Refresh Peta Manual"):
            st.rerun()

    df_turing = pd.read_sql("SELECT * FROM anggota WHERE status_aktif = 1", conn)

    if not df_turing.empty:
        center_lat = df_turing['lat'].mean()
        center_lon = df_turing['lon'].mean()
        
        if pd.isna(center_lat) or pd.isna(center_lon) or (center_lat == 0 and center_lon == 0):
            center_lat, center_lon = -6.2088, 106.8456
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
        
        for idx, row in df_turing.iterrows():
            if row['lat'] is None or row['lon'] is None or (row['lat'] == 0.0 and row['lon'] == 0.0):
                continue
                
            is_me = (row['nama'].lower() == st.session_state.nama_saya.lower())
            
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
        st.info("Belum ada posisi anggota lain yang tercatat di peta.")
