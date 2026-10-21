import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
import math
import requests

# Konfigurasi Halaman
st.set_page_config(page_title="Peta Lokasi Grup & SPBU", layout="wide")
st.title("📍 Live Tracking Lokasi Grup (Google/Email Login)")

# --- 1. DATABASE SQLITE MENGGUNAKAN TABEL VERSI BARU ---
def init_db():
    conn = sqlite3.connect('lokasi_data.db', check_same_thread=False)
    cursor = conn.cursor()
    # Menggunakan nama tabel 'anggota_v2' untuk memastikan struktur PRIMARY KEY bersih dari konflik lama
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS anggota_v2 (
            email TEXT PRIMARY KEY,
            nama TEXT,
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

# --- FUNGSI AMBIL DATA SPBU OVERPASS API (RADIUS 30KM - MAX 500 TITIK) ---
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
                spbu_list.append({
                    "nama": brand,
                    "lat": lat,
                    "lon": lon
                })
        return spbu_list
    except Exception:
        return [
            {"nama": "SPBU Pertamina Rajeg", "lat": -6.1558, "lon": 106.5083},
            {"nama": "SPBU Pertamina Cikupa", "lat": -6.2301, "lon": 106.5234},
            {"nama": "SPBU Rest Area KM 13.5 Tangerang", "lat": -6.2162, "lon": 106.6912},
            {"nama": "SPBU Pertamina Pasar Kemis", "lat": -6.1732, "lon": 106.5412},
            {"nama": "SPBU Shell BSD Boulevard", "lat": -6.3012, "lon": 106.6534},
            {"nama": "SPBU Pertamina Sangiang / Toha", "lat": -6.1780, "lon": 106.6120},
        ]

# --- 2. MANAJEMEN SESI URL & AUTO RECOVERY ---
query_params = st.query_params

if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""

# Recovery sesi dari parameter URL
if st.session_state.user_email == "" and "email" in query_params:
    email_url = query_params["email"]
    cursor = conn.cursor()
    cursor.execute("SELECT email, nama FROM anggota_v2 WHERE email = ? AND status_aktif = 1", (email_url,))
    user_data = cursor.fetchone()
    if user_data:
        st.session_state.user_email = user_data[0]
        st.session_state.user_name = user_data[1]

# Cek integritas sesi (apabila user dikeluarkan oleh admin)
if st.session_state.user_email != "":
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM anggota_v2 WHERE email = ? AND status_aktif = 1", (st.session_state.user_email,))
    active_check = cursor.fetchone()
    if not active_check:
        st.session_state.user_email = ""
        st.session_state.user_name = ""
        st.query_params.clear()

# --- 3. TANGKAP DATA GPS REAL-TIME DARI URL ---
if "lat" in query_params and "lon" in query_params and "email" in query_params and "time" in query_params:
    try:
        u_email = query_params["email"]
        u_lat = float(query_params["lat"])
        u_lon = float(query_params["lon"])
        waktu_sekarang = query_params["time"]
        
        if u_lat != 0.0 and u_lon != 0.0:
            cursor = conn.cursor()
            cursor.execute("SELECT status_aktif FROM anggota_v2 WHERE email = ?", (u_email,))
            res = cursor.fetchone()
            
            if res and res[0] == 1:
                cursor.execute('''
                    UPDATE anggota_v2 SET lat = ?, lon = ?, waktu = ? WHERE email = ?
                ''', (u_lat, u_lon, waktu_sekarang, u_email))
                conn.commit()
    except ValueError:
        pass

# --- SIDEBAR: KONTROL LOGIN EMAIL ---
st.sidebar.header("⚙️ Akses Akun Lokasi")

# JIKA BELUM LOGIN
if st.session_state.user_email == "":
    st.sidebar.info("🔑 Silakan masuk menggunakan Email Google HP kamu untuk mengaktifkan izin bagikan lokasi.")
    
    input_email = st.sidebar.text_input("Alamat Email Google HP:", placeholder="contoh: lian@gmail.com")
    input_nama = st.sidebar.text_input("Nama Panggilan:", placeholder="contoh: Mas Lian")
    
    if st.sidebar.button("🔐 Masuk & Izinkan Lokasi", type="primary"):
        if input_email.strip() != "" and input_nama.strip() != "":
            clean_email = input_email.strip().lower()
            clean_name = input_nama.strip()
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO anggota_v2 (email, nama, lat, lon, waktu, status_aktif)
                VALUES (?, ?, COALESCE((SELECT lat FROM anggota_v2 WHERE email = ?), 0.0), COALESCE((SELECT lon FROM anggota_v2 WHERE email = ?), 0.0), COALESCE((SELECT waktu FROM anggota_v2 WHERE email = ?), 'Mencari Sinyal GPS...'), 1)
            ''', (clean_email, clean_name, clean_email, clean_email, clean_email))
            conn.commit()
            
            st.session_state.user_email = clean_email
            st.session_state.user_name = clean_name
            st.query_params["email"] = clean_email
            st.rerun()
        else:
            st.sidebar.error("Email dan Nama Panggilan wajib diisi!")

    st.info("👋 **Selamat datang!** Silakan *login* melalui sidebar untuk bergabung ke peta lokasi grup.")

# JIKA SUDAH LOGIN
else:
    st.sidebar.success(f"Login sebagai: **{st.session_state.user_name}**")
    st.sidebar.caption(f"📧 {st.session_state.user_email}")
    st.sidebar.caption("📡 GPS & Refresh Peta Serentak Aktif (30 Detik).")
    
    # LOGOUT
    if st.sidebar.button("🚪 Logout / Keluar Sesi", type="primary"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota_v2 WHERE email = ?", (st.session_state.user_email,))
        conn.commit()
        
        st.session_state.user_email = ""
        st.session_state.user_name = ""
        st.query_params.clear()
        
        st.components.v1.html("<script>localStorage.removeItem('lokasi_email'); window.parent.location.href = window.parent.location.pathname;</script>", height=0)
        st.rerun()

    # --- PANEL ADMIN (PIN: 123) ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("🛠️ Panel Admin (PIN: 123)")
    
    df_members = pd.read_sql("SELECT email, nama FROM anggota_v2 WHERE status_aktif = 1", conn)
    member_dict = dict(zip(df_members['nama'], df_members['email'])) if not df_members.empty else {}
    
    st.sidebar.write("👢 **Kick Anggota**")
    selected_name = st.sidebar.selectbox("Pilih Anggota:", options=["-- Pilih --"] + list(member_dict.keys()))
    kick_pin = st.sidebar.text_input("Password Kick:", type="password", key="kick_pin_input")
    
    if st.sidebar.button("🚫 Kick Anggota", type="secondary"):
        if kick_pin == "123":
            if selected_name != "-- Pilih --":
                target_email = member_dict[selected_name]
                cursor = conn.cursor()
                cursor.execute("DELETE FROM anggota_v2 WHERE email = ?", (target_email,))
                conn.commit()
                st.sidebar.success(f"Anggota '{selected_name}' berhasil dikeluarkan!")
                st.rerun()
            else:
                st.sidebar.error("Pilih anggota yang ingin dikeluarkan!")
        else:
            st.sidebar.error("❌ Password salah! (PIN: 123)")

    st.sidebar.markdown("---")
    st.sidebar.write("🗑️ **Reset Semua Anggota**")
    pin_input = st.sidebar.text_input("Password Reset All:", type="password", key="pin_reset_input")
    
    if st.sidebar.button("🔥 Reset Semua", type="secondary"):
        if pin_input == "123":
            cursor = conn.cursor()
            cursor.execute("DELETE FROM anggota_v2")
            conn.commit()
            
            st.session_state.user_email = ""
            st.session_state.user_name = ""
            st.query_params.clear()
            st.success("Semua data sesi berhasil di-reset!")
            
            st.components.v1.html("<script>localStorage.removeItem('lokasi_email'); window.parent.location.href = window.parent.location.pathname;</script>", height=0)
            st.rerun()
        else:
            st.sidebar.error("❌ Password salah! (PIN: 123)")

    st.sidebar.markdown("---")

    # --- DAFTAR ANGGOTA AKTIF ---
    st.sidebar.subheader("📋 Anggota Aktif di Grup")
    df_sidebar = pd.read_sql("SELECT nama, email, lat, lon, waktu FROM anggota_v2 WHERE status_aktif = 1", conn)
    if not df_sidebar.empty:
        st.sidebar.write(f"Total: **{len(df_sidebar)} orang** online")
        for idx, row in df_sidebar.iterrows():
            status_kamu = " (Kamu)" if row['email'] == st.session_state.user_email else ""
            st_gps_info = "🟢 GPS Terhubung" if (row['lat'] != 0.0 and row['lat'] is not None) else "🟡 Mencari Sinyal GPS..."
            st.sidebar.markdown(
                f"📍 **{row['nama']}**{status_kamu}<br>"
                f"<small style='color:gray;'>Status: {st_gps_info}</small><br>"
                f"<small style='color:gray;'>🕒 Update WIB: {row['waktu']}</small>", 
                unsafe_allow_html=True
            )
            st.sidebar.markdown("---")

    # --- SKRIP JAVASCRIPT: AUTO RECOVERY & REAL-TIME GPS SYNC ---
    current_email = st.session_state.user_email
    
    html_gps_script = f"""
    <div style="padding: 10px; background-color: #e8f4f8; border-radius: 6px; font-family: sans-serif; font-size: 13px; border-left: 4px solid #0288d1; margin-bottom: 10px;">
        📡 <b>Izin Share Live Terhubung:</b> Mengirim koordinat GPS & memperbarui jam WIB otomatis tiap 30 detik.
    </div>

    <script>
    const userEmail = "{current_email}";
    
    if (userEmail && userEmail !== "") {{
        localStorage.setItem("lokasi_email", userEmail);
    }}

    const savedEmail = localStorage.getItem("lokasi_email");
    const currentUrlObj = new URL(window.parent.location.href);
    if (savedEmail && !currentUrlObj.searchParams.has("email")) {{
        currentUrlObj.searchParams.set("email", savedEmail);
        window.parent.location.href = currentUrlObj.href;
    }}

    let wakeLock = null;
    async function requestWakeLock() {{
        try {{
            if ('wakeLock' in navigator) {{
                wakeLock = await navigator.wakeLock.request('screen');
            }}
        }} catch (err) {{
            console.log("Wake Lock Error: " + err.message);
        }}
    }}
    requestWakeLock();

    function sendGPSData() {{
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
                    currentUrl.searchParams.set("email", userEmail);
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

    setInterval(sendGPSData, 30000);

    document.addEventListener("visibilitychange", function() {{
        if (document.visibilityState === 'visible') {{
            requestWakeLock();
            sendGPSData();
        }}
    }});
    </script>
    """
    st.components.v1.html(html_gps_script, height=50)

    # --- TAMPILAN PETA BERSAMA ---
    st.subheader("🗺️ Peta Pantauan Anggota & SPBU Radius Max 30 KM")

    df_lokasi = pd.read_sql("SELECT * FROM anggota_v2 WHERE status_aktif = 1", conn)
    df_valid = df_lokasi[(df_lokasi['lat'].notna()) & (df_lokasi['lat'] != 0.0) & (df_lokasi['lon'].notna()) & (df_lokasi['lon'] != 0.0)]

    if not df_valid.empty:
        my_data = df_valid[df_valid['email'] == st.session_state.user_email]
        
        if not my_data.empty:
            center_lat = my_data.iloc[0]['lat']
            center_lon = my_data.iloc[0]['lon']
        else:
            center_lat = df_valid['lat'].mean()
            center_lon = df_valid['lon'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
        
        # 1. MARKER SELURUH ANGGOTA
        for idx, row in df_valid.iterrows():
            is_me = (row['email'] == st.session_state.user_email)
            
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

        # 2. MARKER SPBU (RADIUS MAX 30 KM)
        spbu_data = fetch_nearby_spbu(center_lat, center_lon, radius_km=30)
        spbu_added = set()
        
        for spbu in spbu_data:
            dist = calculate_distance(center_lat, center_lon, spbu['lat'], spbu['lon'])
            
            if dist <= 30.0:
                spbu_key = (round(spbu['lat'], 4), round(spbu['lon'], 4))
                if spbu_key not in spbu_added:
                    spbu_added.add(spbu_key)
                    
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
