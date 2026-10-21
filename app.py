import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3

# Konfigurasi Halaman
st.set_page_config(page_title="Peta Lokasi Privat", layout="wide")
st.title("📍 Live Tracking Lokasi Grup")

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
    st.sidebar.caption("📡 Pelacak GPS Real-Time Aktif (Update tiap 30 detik).")
    
    # TOMBOL LOGOUT PRIBADI
    if st.sidebar.button("🚪 Logout / Keluar Sesi", type="primary"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota WHERE nama = ?", (st.session_state.nama_saya,))
        conn.commit()
        
        st.session_state.nama_saya = ""
        st.query_params.clear()
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
                f"<small style='color:gray;'>🕒 Update (WIB): {row['waktu']}</small>", 
                unsafe_allow_html=True
            )
            st.sidebar.markdown("---")
    else:
        st.sidebar.info("Belum ada anggota lain yang bergabung.")

    # --- SKRIP JAVASCRIPT REAL-TIME GPS (INTERVAL 30 DETIK) ---
    current_user_name = st.session_state.nama_saya
    
    html_realtime_gps = f"""
    <div style="padding: 10px; background-color: #e8f4f8; border-radius: 6px; font-family: sans-serif; font-size: 13px; border-left: 4px solid #0288d1; margin-bottom: 10px;">
        📡 <b>Background Tracker Aktif:</b> Mengirim posisi & jam WIB tiap 30 detik secara senyap.
    </div>

    <script>
    const userName = "{current_user_name}";

    function sendRealtimeGPS() {{
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
                    const prevLat = currentUrl.searchParams.get("lat");
                    
                    currentUrl.searchParams.set("user", userName);
                    currentUrl.searchParams.set("lat", lat);
                    currentUrl.searchParams.set("lon", lon);
                    currentUrl.searchParams.set("time", timeWIB);
                    
                    window.parent.history.replaceState({{}}, '', currentUrl.href);

                    // Auto refresh halaman saat pertama kali koordinat didapat dari HP
                    if (!prevLat || prevLat === "0" || prevLat === "0.0") {{
                        window.parent.location.reload();
                    }}
                }},
                function(error) {{
                    console.log("GPS Error: " + error.message);
                }},
                {{ enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }}
            );
        }}
    }}

    // Eksekusi pertama kali saat dimuat
    sendRealtimeGPS();
    // Sinkronisasi otomatis diatur ulang setiap 30 detik (30000 milidetik)
    setInterval(sendRealtimeGPS, 30000);
    </script>
    """
    st.components.v1.html(html_realtime_gps, height=50)

    # --- TAMPILAN PETA BERSAMA ---
    col_tittle, col_btn = st.columns([3, 1])
    with col_tittle:
        st.subheader("🗺️ Peta Pantauan Anggota Aktif")
    with col_btn:
        st.write("")
        if st.button("🔄 Refresh Peta Manual"):
            st.rerun()

    df_lokasi = pd.read_sql("SELECT * FROM anggota WHERE status_aktif = 1", conn)

    # Hanya ambil data dengan koordinat nyata (bukan 0.0/None)
    df_valid = df_lokasi[(df_lokasi['lat'].notna()) & (df_lokasi['lat'] != 0.0) & (df_lokasi['lon'].notna()) & (df_lokasi['lon'] != 0.0)]

    if not df_valid.empty:
        center_lat = df_valid['lat'].mean()
        center_lon = df_valid['lon'].mean()
        
        m = folium.Map(location=[center_lat, center_lon], zoom_start=15)
        
        for idx, row in df_valid.iterrows():
            is_me = (row['nama'].lower() == st.session_state.nama_saya.lower())
            
            warna_marker = 'red' if is_me else 'blue'
            ikon_simbol = 'user' if is_me else 'map-marker'
            
            popup_html = f"<b>{row['nama']}</b> {'(Kamu)' if is_me else ''}<br><small>Update (WIB): {row['waktu']}</small><br><small>Lat: {row['lat']:.5f}, Lon: {row['lon']:.5f}</small>"
            
            folium.Marker(
                [row['lat'], row['lon']], 
                popup=folium.Popup(popup_html, max_width=220),
                tooltip=f"{row['nama']} (Akurat)",
                icon=folium.Icon(color=warna_marker, icon=ikon_simbol, prefix='fa')
            ).add_to(m)

            folium.Circle(
                location=[row['lat'], row['lon']],
                radius=50,
                color='red' if is_me else 'blue',
                fill=True,
                fill_opacity=0.2
            ).add_to(m)

        st_folium(m, width=1100, height=520)

    else:
        st.warning("📡 **Sedang mengambil lokasi presisi dari HP kamu...**")
        st.info("Pastikan kamu mengeklik tombol **Allow / Izinkan Lokasi** pada pop-up izin browser HP. Jika peta belum muncul, klik tombol **Refresh Peta Manual** di kanan atas.")
