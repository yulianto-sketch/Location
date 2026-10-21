import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
import math

# Konfigurasi Halaman
st.set_page_config(page_title="Peta Lokasi Privat", layout="wide")
st.title("📍 Live Tracking Lokasi Grup & SPBU Radius 50km")

# --- 1. DATABASE SQLITE & MIGRASI SKEMA OTOMATIS ---
def init_db():
    conn = sqlite3.connect('lokasi_data.db', check_same_thread=False)
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
    try:
        cursor.execute("ALTER TABLE anggota ADD COLUMN status_aktif INTEGER DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn

conn = init_db()

# --- FUNGSI HITUNG JARAK (HAVERSINE FORMULA) ---
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371.0 # Radius bumi dalam KM
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- DATABASE / DAFTAR SPBU BESAR ---
SPBU_LIST = [
    {"nama": "SPBU Pertamina Pasti Pas Rajeg", "lat": -6.1558, "lon": 106.5083},
    {"nama": "SPBU Pertamina Cikupa", "lat": -6.2301, "lon": 106.5234},
    {"nama": "SPBU Rest Area KM 13.5 Tol Jakarta-Tangerang", "lat": -6.2162, "lon": 106.6912},
    {"nama": "SPBU Rest Area KM 43 Tol Tangerang-Merak", "lat": -6.2575, "lon": 106.3980},
    {"nama": "SPBU Rest Area KM 68 Tol Tangerang-Merak", "lat": -6.1384, "lon": 106.1925},
    {"nama": "SPBU Pertamina Bandara Soekarno-Hatta", "lat": -6.1265, "lon": 106.6548},
    {"nama": "SPBU Shell BSD Boulevard", "lat": -6.3012, "lon": 106.6534},
    {"nama": "SPBU Pertamina Puncak Bogor", "lat": -6.6983, "lon": 106.9231},
]

# --- 2. BACA URL PARAMETER UNTUK AUTO-LOGIN BUKA TAB BARU ---
query_params = st.query_params

if "nama_saya" not in st.session_state:
    st.session_state.nama_saya = ""

# Auto-recovery sesi jika ada parameter user di URL
if st.session_state.nama_saya == "" and "user" in query_params:
    user_from_url = query_params["user"]
    cursor = conn.cursor()
    cursor.execute("SELECT nama FROM anggota WHERE nama = ? AND status_aktif = 1", (user_from_url,))
    valid_user = cursor.fetchone()
    if valid_user:
        st.session_state.nama_saya = valid_user[0]

# --- 3. CEK INTEGRITAS SESI (LOGOUT OTOMATIS JIKA DI-RESET ADMIN) ---
if st.session_state.nama_saya != "":
    cursor = conn.cursor()
    cursor.execute("SELECT nama FROM anggota WHERE nama = ? AND status_aktif = 1", (st.session_state.nama_saya,))
    active_user = cursor.fetchone()
    if not active_user:
        st.session_state.nama_saya = ""
        st.query_params.clear()

# --- 4. TANGKAP DATA GPS REAL-TIME DARI PARAMETER URL ---
if "lat" in query_params and "lon" in query_params and "user" in query_params and "time" in query_params:
    try:
        u_name = query_params["user"]
        u_lat = float(query_params["lat"])
        u_lon = float(query_params["lon"])
        waktu_sekarang = query_params["time"]
        
        if u_lat != 0.0 and u_lon != 0.0:
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
            cursor.execute("SELECT nama FROM anggota WHERE nama = ? AND status_aktif = 1", (clean_name,))
            existing = cursor.fetchone()
            
            if existing:
                st.sidebar.error("❌ Nama tersebut sedang aktif digunakan. Gunakan nama panggilan lain.")
            else:
                st.session_state.nama_saya = clean_name
                cursor.execute('''
                    INSERT OR REPLACE INTO anggota (nama, lat, lon, waktu, status_aktif)
                    VALUES (?, ?, ?, ?, ?)
                ''', (clean_name, 0.0, 0.0, "Mencari Sinyal GPS Real...", 1))
                conn.commit()
                
                st.query_params["user"] = clean_name
                st.rerun()
        else:
            st.sidebar.error("Nama tidak boleh kosong!")

    st.info("👋 **Selamat datang!** Masukkan nama kamu di sidebar kiri untuk masuk ke peta grup lokasi.")

# JIKA SUDAH LOGIN
else:
    st.sidebar.success(f"Aktif sebagai: **{st.session_state.nama_saya}**")
    st.sidebar.caption("📡 Sync GPS Serentak Aktif (Update & Auto Refresh tiap 30 detik).")
    
    # TOMBOL LOGOUT PRIBADI
    if st.sidebar.button("🚪 Logout / Keluar Sesi", type="primary"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota WHERE nama = ?", (st.session_state.nama_saya,))
        conn.commit()
        
        st.session_state.nama_saya = ""
        st.query_params.clear()
        
        st.components.v1.html("<script>localStorage.removeItem('lokasi_user'); window.parent.location.href = window.parent.location.pathname;</script>", height=0)
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
            st.query_params.clear()
            st.success("Semua data sesi berhasil di-reset untuk semua orang!")
            
            st.components.v1.html("<script>localStorage.removeItem('lokasi_user'); window.parent.location.href = window.parent.location.pathname;</script>", height=0)
            st.rerun()
        else:
            st.sidebar.error("❌ Kode PIN salah! (Gunakan kode: 123)")

    st.sidebar.markdown("---")

    # --- DAFTAR ANGGOTA AKTIF ---
    st.sidebar.subheader("📋 Anggota Aktif di Grup")
    df_sidebar = pd.read_sql("SELECT nama, lat, lon, waktu FROM anggota WHERE status_aktif = 1", conn)
    if not df_sidebar.empty:
        st.sidebar.write(f"Total: **{len(df_sidebar)} orang** online")
        for idx, row in df_sidebar.iterrows():
            status_kamu = " (Kamu)" if row['nama'] == st.session_state.nama_saya else ""
            st_gps_info = "🟢 GPS Terhubung" if (row['lat'] != 0.0 and row['lat'] is not None) else "🟡 Mencari Sinyal GPS..."
            st.sidebar.markdown(
                f"📍 **{row['nama']}**{status_kamu}<br>"
                f"<small style='color:gray;'>Status: {st_gps_info}</small><br>"
                f"<small style='color:gray;'>🕒 Update WIB: {row['waktu']}</small>", 
                unsafe_allow_html=True
            )
            st.sidebar.markdown("---")
    else:
        st.sidebar.info("Belum ada anggota lain yang bergabung.")

    # --- SKRIP JAVASCRIPT: SYNC SINKRONISASI SERENTAK TIAP DETIK 00 & 30 ---
    current_user_name = st.session_state.nama_saya
    
    html_synchronized_gps = f"""
    <div style="padding: 10px; background-color: #e8f4f8; border-radius: 6px; font-family: sans-serif; font-size: 13px; border-left: 4px solid #0288d1; margin-bottom: 10px;">
        📡 <b>Sync GPS Serentak & Auto-Refresh:</b> Mengirim koordinat WIB bersamaan di detik :00 & :30 dan merefresh peta secara otomatis.
    </div>

    <script>
    const userName = "{current_user_name}";
    
    if (userName && userName !== "") {{
        localStorage.setItem("lokasi_user", userName);
    }}

    const savedUser = localStorage.getItem("lokasi_user");
    const currentUrlObj = new URL(window.parent.location.href);
    if (savedUser && !currentUrlObj.searchParams.has("user")) {{
        currentUrlObj.searchParams.set("user", savedUser);
        window.parent.location.href = currentUrlObj.href;
    }}

    function sendSynchronizedGPS() {{
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
                    
                    // Lakukan pencatatan parameter & trigger reload halaman agar peta langsung ter-update otomatis bersamaan
                    window.parent.location.href = currentUrl.href;
                }},
                function(error) {{
                    console.log("GPS Error: " + error.message);
                }},
                {{ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }}
            );
        }}
    }}

    // Menghitung jeda milidetik menuju detik ke-00 atau detik ke-30 berikutnya (Sinkronisasi Serentak Semua HP)
    function scheduleNextSync() {{
        const now = new Date();
        const currentSeconds = now.getSeconds();
        const currentMillis = now.getMilliseconds();
        
        let secondsToWait = 30 - (currentSeconds % 30);
        let timeToNextSync = (secondsToWait * 1000) - currentMillis;

        setTimeout(function() {{
            sendSynchronizedGPS();
        }}, timeToNextSync);
    }}

    scheduleNextSync();
    </script>
    """
    st.components.v1.html(html_synchronized_gps, height=50)

    # --- TAMPILAN PETA BERSAMA ---
    st.subheader("🗺️ Peta Pantauan Anggota & SPBU Besar (Auto Refresh 30s)")

    df_lokasi = pd.read_sql("SELECT * FROM anggota WHERE status_aktif = 1", conn)
    df_valid = df_lokasi[(df_lokasi['lat'].notna()) & (df_lokasi['lat'] != 0.0) & (df_lokasi['lon'].notna()) & (df_lokasi['lon'] != 0.0)]

    if not df_valid.empty:
        center_lat = df_valid['lat'].mean()
        center_lon = df_valid['lon'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
        
        # 1. MARKER ANGGOTA
        for idx, row in df_valid.iterrows():
            is_me = (row['nama'].lower() == st.session_state.nama_saya.lower())
            
            warna_marker = 'red' if is_me else 'blue'
            ikon_simbol = 'user' if is_me else 'map-marker'
            
            popup_html = f"<b>{row['nama']}</b> {'(Kamu)' if is_me else ''}<br><small>Update (WIB): {row['waktu']}</small><br><small>Lat: {row['lat']:.5f}, Lon: {row['lon']:.5f}</small>"
            
            folium.Marker(
                [row['lat'], row['lon']], 
                popup=folium.Popup(popup_html, max_width=220),
                tooltip=f"{row['nama']} ({row['waktu']} WIB)",
                icon=folium.Icon(color=warna_marker, icon=ikon_simbol, prefix='fa')
            ).add_to(m)

            folium.Circle(
                location=[row['lat'], row['lon']],
                radius=100,
                color='red' if is_me else 'blue',
                fill=True,
                fill_opacity=0.2
            ).add_to(m)

        # 2. MARKER SPBU BESAR (RADIUS 50 KM)
        spbu_added = set()
        for _, member in df_valid.iterrows():
            m_lat, m_lon = member['lat'], member['lon']
            
            for spbu in SPBU_LIST:
                dist = calculate_distance(m_lat, m_lon, spbu['lat'], spbu['lon'])
                if dist <= 50.0:
                    spbu_key = (spbu['lat'], spbu['lon'])
                    if spbu_key not in spbu_added:
                        spbu_added.add(spbu_key)
                        
                        popup_spbu = f"⛽ <b>{spbu['nama']}</b><br><small>Jarak: ~{dist:.1f} km dari {member['nama']}</small>"
                        folium.Marker(
                            [spbu['lat'], spbu['lon']],
                            popup=folium.Popup(popup_spbu, max_width=220),
                            tooltip=f"⛽ {spbu['nama']} ({dist:.1f} km)",
                            icon=folium.Icon(color='orange', icon='gas-pump', prefix='fa')
                        ).add_to(m)

        st_folium(m, width=1100, height=520, key="live_map")

    else:
        st.warning("📡 **Sedang menyingkronkan lokasi presisi dari HP kamu...**")
        st.info("Pastikan kamu mengeklik tombol **Allow / Izinkan Lokasi** pada pop-up izin browser HP.")
