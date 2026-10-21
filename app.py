import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
import math
import requests

# Konfigurasi Halaman
st.set_page_config(page_title="Peta Touring & SPBU", layout="wide")
st.title("📍 Live Tracking Touring Rombongan")

# --- 1. INISIALISASI DATABASE SQLITE (BERBASIS NAMA UNIK) ---
def init_db():
    conn = sqlite3.connect('lokasi_touring.db', check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS peserta (
            nama TEXT PRIMARY KEY,
            lat REAL,
            lon REAL,
            waktu TEXT,
            status_aktif INTEGER DEFAULT 1
        )
    ''')
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

# --- FUNGSI AMBIL DATA SPBU OVERPASS API (RADIUS 30KM) ---
@st.cache_data(ttl=300)
def fetch_nearby_spbu(center_lat, center_lon, radius_km=30):
    radius_meters = int(radius_km * 1000)
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    query = f"""
    [out:json][timeout:25];
    (
      node["amenity"="fuel"](around:{radius_meters},{center_lat},{center_lon});
      way["amenity"="fuel"](around:{radius_meters},{center_lat},{center_lon});
    );
    out center 500;
    """
    try:
        resp = requests.post(overpass_url, data={'data': query}, timeout=20)
        data = resp.json()
        spbu_list = []
        for element in data.get('elements', []):
            lat = element.get('lat') or element.get('center', {}).get('lat')
            lon = element.get('lon') or element.get('center', {}).get('lon')
            tags = element.get('tags', {})
            brand = tags.get('name') or tags.get('brand') or tags.get('operator') or 'SPBU / Pom Bensin'
                
            if lat and lon:
                spbu_list.append({"nama": brand, "lat": lat, "lon": lon})
        return spbu_list
    except Exception:
        return [
            {"nama": "SPBU Pertamina Rajeg", "lat": -6.1558, "lon": 106.5083},
            {"nama": "SPBU Pertamina Cikupa", "lat": -6.2301, "lon": 106.5234},
            {"nama": "SPBU Rest Area KM 13.5", "lat": -6.2162, "lon": 106.6912},
            {"nama": "SPBU Shell BSD", "lat": -6.3012, "lon": 106.6534},
        ]

# --- 2. MANAJEMEN SESI BERBASIS NAMA ---
query_params = st.query_params

if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# Recovery sesi dari parameter URL
if st.session_state.user_name == "" and "nama" in query_params:
    nama_url = query_params["nama"]
    cursor = conn.cursor()
    cursor.execute("SELECT nama FROM peserta WHERE nama = ? AND status_aktif = 1", (nama_url,))
    user_data = cursor.fetchone()
    if user_data:
        st.session_state.user_name = user_data[0]

# --- 3. TANGKAP DATA GPS DARI URL ---
if "lat" in query_params and "lon" in query_params and "nama" in query_params and "time" in query_params:
    try:
        u_nama = query_params["nama"]
        u_lat = float(query_params["lat"])
        u_lon = float(query_params["lon"])
        waktu_sekarang = query_params["time"]
        
        if u_lat != 0.0 and u_lon != 0.0:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE peserta SET lat = ?, lon = ?, waktu = ? WHERE nama = ?
            ''', (u_lat, u_lon, waktu_sekarang, u_nama))
            conn.commit()
    except ValueError:
        pass

# --- SIDEBAR: KONTROL MASUK & ADMIN ---
st.sidebar.header("⚙️ Konfigurasi Touring")

if st.session_state.user_name == "":
    st.sidebar.info("👋 Masukkan nama panggilan unik untuk mulai membagikan lokasi.");
    
    input_nama = st.sidebar.text_input("Nama Panggilan:", placeholder="Contoh: Mas Lian")
    
    if st.sidebar.button("🚀 Gabung ke Peta", type="primary"):
        if input_nama.strip() != "":
            clean_name = input_nama.strip()
            
            cursor = conn.cursor()
            # Cek apakah nama sudah dipakai orang lain
            cursor.execute("SELECT nama FROM peserta WHERE nama = ?", (clean_name,))
            existing = cursor.fetchone()
            
            if existing:
                st.sidebar.error("❌ Nama tersebut sudah dipakai peserta lain! Gunakan nama lain agar tidak kembar.")
            else:
                cursor.execute('''
                    INSERT INTO peserta (nama, lat, lon, waktu, status_aktif)
                    VALUES (?, 0.0, 0.0, 'Mencari Sinyal...', 1)
                ''', (clean_name,))
                conn.commit()
                
                st.session_state.user_name = clean_name
                st.query_params["nama"] = clean_name
                st.rerun()
        else:
            st.sidebar.error("Nama panggilan wajib diisi!")
else:
    st.sidebar.success(f"Status: Bergabung sebagai **{st.session_state.user_name}**")
    
    if st.sidebar.button("🚪 Keluar / Ganti Nama", type="secondary"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM peserta WHERE nama = ?", (st.session_state.user_name,))
        conn.commit()
        
        st.session_state.user_name = ""
        st.query_params.clear()
        st.rerun()

    # --- PANEL ADMIN (PIN: 123) ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Panel Admin (PIN: 123)")
    
    df_members = pd.read_sql("SELECT nama FROM peserta WHERE status_aktif = 1", conn)
    member_list = df_members['nama'].tolist() if not df_members.empty else []
    
    kick_target = st.sidebar.selectbox("Pilih Anggota:", options=["-- Pilih --"] + member_list)
    admin_pin = st.sidebar.text_input("PIN Admin:", type="password")
    
    if st.sidebar.button("🚫 Keluarkan Anggota"):
        if admin_pin == "123":
            if kick_target != "-- Pilih --":
                cursor = conn.cursor()
                cursor.execute("DELETE FROM peserta WHERE nama = ?", (kick_target,))
                conn.commit()
                st.sidebar.success(f"'{kick_target}' dikeluarkan dari rombongan.")
                st.rerun()
            else:
                st.sidebar.error("Pilih anggota yang mau di-kick!")
        else:
            st.sidebar.error("❌ PIN Salah!")

    if st.sidebar.button("🔥 Reset Semua Data"):
        if admin_pin == "123":
            cursor = conn.cursor()
            cursor.execute("DELETE FROM peserta")
            conn.commit()
            st.session_state.user_name = ""
            st.query_params.clear()
            st.rerun()
        else:
            st.sidebar.error("❌ PIN Salah!")

    # --- DAFTAR ANGGOTA DI SIDEBAR ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("📋 Anggota Online")
    df_sidebar = pd.read_sql("SELECT nama, lat, waktu FROM peserta", conn)
    if not df_sidebar.empty:
        for idx, row in df_sidebar.iterrows():
            status_ T = "🟢 Terhubung" if row['lat'] != 0.0 else "🟡 Menunggu GPS..."
            is_me = " (Kamu)" if row['nama'] == st.session_state.user_name else ""
            st.sidebar.markdown(f"**{row['nama']}**{is_me}<br><small>{status_T} | {row['waktu']}</small>", unsafe_allow_html=True)

    # --- SKRIP JAVASCRIPT: AUTO SYNC GPS (SETIAP 30 DETIK) ---
    current_user = st.session_state.user_name
    html_gps_script = f"""
    <script>
    const userName = "{current_user}";
    
    function sendGPS() {{
        if (navigator.geolocation) {{
            navigator.geolocation.getCurrentPosition(
                function(pos) {{
                    const lat = pos.coords.latitude;
                    const lon = pos.coords.longitude;
                    const now = new Date();
                    const timeWIB = String(now.getHours()).padStart(2, '0') + ":" + 
                                    String(now.getMinutes()).padStart(2, '0') + ":" + 
                                    String(now.getSeconds()).padStart(2, '0');
                    
                    const url = new URL(window.parent.location.href);
                    url.searchParams.set("nama", userName);
                    url.searchParams.set("lat", lat);
                    url.searchParams.set("lon", lon);
                    url.searchParams.set("time", timeWIB);
                    window.parent.location.href = url.href;
                }},
                function(err) {{ console.log("GPS Error: " + err.message); }},
                {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
            );
        }}
    }}
    setInterval(sendGPS, 30000);
    </script>
    """
    st.components.v1.html(html_gps_script, height=0)

# --- TAMPILAN UTAMA PETA ---
st.subheader("🗺️ Peta Lokasi Rombongan & Titik SPBU")

df_lokasi = pd.read_sql("SELECT * FROM peserta WHERE status_aktif = 1", conn)
df_valid = df_lokasi[(df_lokasi['lat'].notna()) & (df_lokasi['lat'] != 0.0)]

if not df_valid.empty:
    my_data = df_valid[df_valid['nama'] == st.session_state.user_name]
    center_lat = my_data.iloc[0]['lat'] if not my_data.empty else df_valid['lat'].mean()
    center_lon = my_data.iloc[0]['lon'] if not my_data.empty else df_valid['lon'].mean()
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    # Marker Anggota
    for idx, row in df_valid.iterrows():
        is_me = (row['nama'] == st.session_state.user_name)
        color = 'red' if is_me else 'blue'
        
        popup_text = f"<b>{row['nama']}</b> {'(Kamu)' if is_me else ''}<br>Update: {row['waktu']} WIB"
        folium.Marker(
            [row['lat'], row['lon']],
            popup=folium.Popup(popup_text, max_width=200),
            tooltip=row['nama'],
            icon=folium.Icon(color=color, icon='user' if is_me else 'map-marker', prefix='fa')
        ).add_to(m)
        
        folium.Circle([row['lat'], row['lon']], radius=80, color=color, fill=True, fill_opacity=0.2).add_to(m)

    # Marker SPBU (Radius 30 KM)
    spbu_list = fetch_nearby_spbu(center_lat, center_lon, radius_km=30)
    for spbu in spbu_list:
        dist = calculate_distance(center_lat, center_lon, spbu['lat'], spbu['lon'])
        if dist <= 30.0:
            color_spbu = 'yellow' if 'pertamina' in spbu['nama'].lower() else 'orange'
            folium.Marker(
                [spbu['lat'], spbu['lon']],
                popup=f"⛽ <b>{spbu['nama']}</b><br>Jarak: ~{dist:.1f} km",
                tooltip=spbu['nama'],
                icon=folium.Icon(color=color_spbu, icon='gas-pump', prefix='fa')
            ).add_to(m)

    st_folium(m, width=1100, height=500, key="tour_map")
else:
    st.warning("📡 Menunggu sinyal GPS dari perangkat Anda. Pastikan izin lokasi (*Allow*) di browser sudah aktif.")
