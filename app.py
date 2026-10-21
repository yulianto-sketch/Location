import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
import math
import requests

# Konfigurasi Halaman
st.set_page_config(page_title="Peta Lokasi Privat", layout="wide")
st.title("📍 Live Tracking Lokasi Grup & SPBU Radius 30km")

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

# --- FUNGSI AMBIL SEMUA SPBU REAL-TIME (RADIUS 30KM) ---
@st.cache_data(ttl=300) # Cache 5 menit agar cepat & tidak membebani koneksi
def fetch_nearby_spbu(center_lat, center_lon, radius_km=30):
    radius_meters = int(radius_km * 1000)
    overpass_url = "https://overpass-api.de/api/interpreter"
    
    # Query lengkap untuk mengambil hingga 300 SPBU dalam radius 30 km
    query = f"""
    [out:json][timeout:20];
    (
      node["amenity"="fuel"](around:{radius_meters},{center_lat},{center_lon});
      way["amenity"="fuel"](around:{radius_meters},{center_lat},{center_lon});
      relation["amenity"="fuel"](around:{radius_meters},{center_lat},{center_lon});
    );
    out center 300;
    """
    try:
        resp = requests.post(overpass_url, data={'data': query}, timeout=15)
        data = resp.json()
        spbu_list = []
        for element in data.get('elements', []):
            lat = element.get('lat') or element.get('center', {}).get('lat')
            lon = element.get('lon') or element.get('center', {}).get('lon')
            tags = element.get('tags', {})
            
            # Deteksi nama SPBU / Brand
            brand = tags.get('brand', tags.get('operator', tags.get('name', 'SPBU / Pom Bensin')))
            if brand in ['SPBU / Pom Bensin', 'fuel'] and tags.get('name'):
                brand = tags.get('name')
                
            if lat and lon:
                spbu_list.append({
                    "nama": brand,
                    "lat": lat,
                    "lon": lon
                })
        return spbu_list
    except Exception:
        # Fallback daftar SPBU utama jika koneksi server API sibuk
        return [
            {"nama": "SPBU Pertamina Rajeg", "lat": -6.1558, "lon": 106.5083},
            {"nama": "SPBU Pertamina Cikupa", "lat": -6.2301, "lon": 106.5234},
            {"nama": "SPBU Rest Area KM 13.5 Tangerang", "lat": -6.2162, "lon": 106.6912},
            {"nama": "SPBU Pertamina Pasar Kemis", "lat": -6.1732, "lon": 106.5412},
            {"nama": "SPBU Shell BSD Boulevard", "lat": -6.3012, "lon": 106.6534},
            {"nama": "SPBU Pertamina Balaraja", "lat": -6.1912, "lon": 106.4521},
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

# --- 3. CEK INTEGRITAS SESI (LOGOUT OTOMATIS JIKA DI-KICK / DI-RESET ADMIN) ---
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
    st.sidebar.caption("📡 Sync GPS & Refresh Peta Serentak Aktif (tiap 30 detik).")
    
    # TOMBOL LOGOUT PRIBADI
    if st.sidebar.button("🚪 Logout / Keluar Sesi", type="primary"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota WHERE nama = ?", (st.session_state.nama_saya,))
        conn.commit()
        
        st.session_state.nama_saya = ""
        st.query_params.clear()
        
        st.components.v1.html("<script>localStorage.removeItem('lokasi_user'); window.parent.location.href = window.parent.location.pathname;</script>", height=0)
        st.rerun()

    # --- PANEL KICK ANGGOTA & RESET ALL (PASSWORD: 123) ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Panel Admin (PIN: 123)")
    
    df_members = pd.read_sql("SELECT nama FROM anggota WHERE status_aktif = 1", conn)
    member_list = df_members['nama'].tolist() if not df_members.empty else []
    
    # 1. KICK ANGGOTA MANUAL
    st.sidebar.write("👢 **Kick Anggota**")
    selected_member = st.sidebar.selectbox("Pilih Anggota:", options=["-- Pilih --"] + member_list)
    kick_pin = st.sidebar.text_input("Password Kick:", type="password", key="kick_pin_input")
    
    if st.sidebar.button("🚫 Kick Anggota", type="secondary"):
        if kick_pin == "123":
            if selected_member != "-- Pilih --":
                cursor = conn.cursor()
                cursor.execute("DELETE FROM anggota WHERE nama = ?", (selected_member,))
                conn.commit()
                st.sidebar.success(f"Anggota '{selected_member}' berhasil dikeluarkan!")
                st.rerun()
            else:
                st.sidebar.error("Pilih anggota yang ingin dikeluarkan!")
        else:
            st.sidebar.error("❌ Password salah! (PIN: 123)")

    # 2. RESET SEMUA ANGGOTA
    st.sidebar.markdown("---")
    st.sidebar.write("🗑️ **Reset Semua Anggota**")
    pin_input = st.sidebar.text_input("Password Reset All:", type="password", key="pin_reset_input")
    
    if st.sidebar.button("🔥 Reset Semua", type="secondary"):
        if pin_input == "123":
            cursor = conn.cursor()
            cursor.execute("DELETE FROM anggota")
            conn.commit()
            
            st.session_state.nama_saya = ""
            st.query_params.clear()
            st.success("Semua data sesi berhasil di-reset!")
            
            st.components.v1.html("<script>localStorage.removeItem('lokasi_user'); window.parent.location.href = window.parent.location.pathname;</script>", height=0)
            st.rerun()
        else:
            st.sidebar.error("❌ Password salah! (PIN: 123)")

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

    # --- SKRIP JAVASCRIPT: UPDATE GPS & AUTO-RELOAD HARIAN SETIAP 30 DETIK ---
    current_user_name = st.session_state.nama_saya
    
    html_synchronized_gps = f"""
    <div style="padding: 10px; background-color: #e8f4f8; border-radius: 6px; font-family: sans-serif; font-size: 13px; border-left: 4px solid #0288d1; margin-bottom: 10px;">
        📡 <b>Sync GPS Serentak:</b> Mengirim koordinat & memperbarui WIB secara otomatis tiap 30 detik.
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
                    
                    window.parent.location.href = currentUrl.href;
                }},
                function(error) {{
                    console.log("GPS Error: " + error.message);
                }},
                {{ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }}
            );
        }}
    }}

    setInterval(sendSynchronizedGPS, 30000);
    </script>
    """
    st.components.v1.html(html_synchronized_gps, height=50)

    # --- TAMPILAN PETA BERSAMA ---
    st.subheader("🗺️ Peta Pantauan Anggota & SPBU Radius Max 30 KM")

    df_lokasi = pd.read_sql("SELECT * FROM anggota WHERE status_aktif = 1", conn)
    df_valid = df_lokasi[(df_lokasi['lat'].notna()) & (df_lokasi['lat'] != 0.0) & (df_lokasi['lon'].notna()) & (df_lokasi['lon'] != 0.0)]

    if not df_valid.empty:
        my_data = df_valid[df_valid['nama'].str.lower() == st.session_state.nama_saya.lower()]
        
        if not my_data.empty:
            center_lat = my_data.iloc[0]['lat']
            center_lon = my_data.iloc[0]['lon']
        else:
            center_lat = df_valid['lat'].mean()
            center_lon = df_valid['lon'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
        
        # 1. MARKER SELURUH ANGGOTA
        for idx, row in df_valid.iterrows():
            is_me = (row['nama'].lower() == st.session_state.nama_saya.lower())
            
            warna_marker = 'red' if is_me else 'blue'
            ikon_simbol = 'user' if is_me else 'map-marker'
            
            popup_html = f"<b>{row['nama']}</b> {'(Kamu)' if is_me else ''}<br><small>Update WIB: {row['waktu']}</small><br><small>Lat: {row['lat']:.5f}, Lon: {row['lon']:.5f}</small>"
            
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

        # 2. MARKER SPBU LENGKAP DI RADIUS MAX 30 KM
        spbu_data = fetch_nearby_spbu(center_lat, center_lon, radius_km=30)
        spbu_added = set()
        
        for spbu in spbu_data:
            dist = calculate_distance(center_lat, center_lon, spbu['lat'], spbu['lon'])
            
            # Filter ketat maksimal 30 KM dari titik user login
            if dist <= 30.0:
                spbu_key = (round(spbu['lat'], 4), round(spbu['lon'], 4))
                if spbu_key not in spbu_added:
                    spbu_added.add(spbu_key)
                    
                    # Warna Kuning untuk Pertamina, Warna Oranye untuk Merek Lain
                    nama_spbu_lower = spbu['nama'].lower()
                    if 'pertamina' in nama_spbu_lower:
                        warna_spbu = 'yellow'
                    else:
                        warna_spbu = 'orange'
                    
                    popup_spbu = f"⛽ <b>{spbu['nama']}</b><br><small>Jarak: ~{dist:.1f} km dari posisi kamu</small>"
                    folium.Marker(
                        [spbu['lat'], spbu['lon']],
                        popup=folium.Popup(popup_spbu, max_width=220),
                        tooltip=f"⛽ {spbu['nama']} ({dist:.1f} km)",
                        icon=folium.Icon(color=warna_spbu, icon='gas-pump', prefix='fa')
                    ).add_to(m)

        st_folium(m, width=1100, height=520, key="live_map")

    else:
        st.warning("📡 **Sedang menyingkronkan lokasi presisi dari HP kamu...**")
        st.info("Pastikan kamu mengeklik tombol **Allow / Izinkan Lokasi** pada pop-up izin browser HP.")
