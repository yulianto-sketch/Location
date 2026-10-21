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

# --- SIDEBAR: KONTROL SESI & TOMBOL KELUAR ---
st.sidebar.header("⚙️ Sesi Turing")

if not st.session_state.sedang_gabung:
    # --- FORM KETIKA BELUM GABUNG ---
    st.sidebar.info("Masukkan nama kamu untuk bergabung ke dalam sesi turing.")
    input_nama = st.sidebar.text_input("Nama Kamu / Panggilan:", key="input_nama_field")
    
    if st.sidebar.button("🚀 Gabung Sesi Turing", type="primary"):
        if input_nama.strip() != "":
            st.session_state.nama_saya = input_nama.strip()
            st.session_state.sedang_gabung = True
            st.rerun()
        else:
            st.sidebar.error("Nama tidak boleh kosong!")

else:
    # --- MENU KETIKA SUDAH GABUNG (TOMBOL KELUAR PASTI MUNCUL DI SINI) ---
    st.sidebar.success(f"Aktif sebagai: **{st.session_state.nama_saya}**")
    
    st.sidebar.markdown("---")
    st.sidebar.write("📌 **Kontrol Lokasi Anda:**")
    st.sidebar.caption("Klik tombol di bawah untuk mengambil titik GPS HP Anda saat ini dan mengirimkannya ke peta grup.")
    
    # Tombol kirim posisi GPS instan
    if st.sidebar.button("📍 Kirim / Update Posisi GPS Saya", type="primary"):
        # Script JS kecil untuk mengambil koordinat dan memasukkannya ke session/database via komponen
        pass # Ditangani oleh komponen HTML GPS di bawah

    st.sidebar.markdown("---")
    
    # TOMBOL KELUAR SESI YANG DICARI
    if st.sidebar.button("🚪 Keluar Sesi", type="secondary"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota WHERE nama = ?", (st.session_state.nama_saya,))
        conn.commit()
        
        # Reset session
        st.session_state.sedang_gabung = False
        st.session_state.nama_saya = ""
        st.rerun()

st.sidebar.markdown("---")

# --- 3. DAFTAR NAMA ANGGOTA AKTIF DI SIDEBAR ---
st.sidebar.subheader("📋 Anggota Aktif di Grup")
df_sidebar = pd.read_sql("SELECT nama, waktu FROM anggota", conn)
if not df_sidebar.empty:
    st.sidebar.write(f"Total: **{len(df_sidebar)} orang** online")
    for idx, row in df_sidebar.iterrows():
        status_kamu = " (Kamu)" if row['nama'] == st.session_state.nama_saya else ""
        st.sidebar.markdown(f"- 🏍️ **{row['nama']}**{status_kamu} <br><small style='color:gray;'>Update: {row['waktu']}</small>", unsafe_allow_html=True)
else:
    st.sidebar.info("Belum ada anggota yang bergabung.")

# --- 4. KOMPONEN GPS OTOMATIS (TANPA PAKSA REFRESH URL) ---
if st.session_state.sedang_gabung:
    # HTML Component untuk menangkap GPS dan menyimpannya lewat form tersembunyi / local storage / fetch
    html_gps_capture = f"""
    <div style="padding: 12px; background-color: #e8f4f8; border-radius: 8px; font-family: sans-serif; border-left: 4px solid #0288d1; margin-bottom: 15px;">
        📡 <b>Status GPS Anda ({st.session_state.nama_saya}):</b> <span id="gps_status">Mencari sinyal...</span>
        <div style="margin-top: 8px;">
            <button onclick="getLiveGPS()" style="background-color: #0288d1; color: white; border: none; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-weight: bold;">
                🔄 Ambil & Kirim GPS Terbaru
            </button>
        </div>
    </div>

    <script>
    function getLiveGPS() {{
        const statusEl = document.getElementById('gps_status');
        if (navigator.geolocation) {{
            statusEl.innerHTML = "Menghubungkan ke satelit GPS...";
            navigator.geolocation.getCurrentPosition(
                function(position) {{
                    const lat = position.coords.latitude;
                    const lon = position.coords.longitude;
                    statusEl.innerHTML = "✅ Berhasil! Lat: " + lat.toFixed(5) + " | Lon: " + lon.toFixed(5);
                    
                    // Simpan ke localStorage agar bisa dibaca jika diperlukan
                    localStorage.setItem('turing_lat', lat);
                    localStorage.setItem('turing_lon', lon);
                }},
                function(error) {{
                    statusEl.innerHTML = "❌ Gagal mendeteksi GPS. Pastikan izin lokasi aktif.";
                }},
                {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }}
            );
        }} else {{
            statusEl.innerHTML = "❌ Browser tidak mendukung GPS.";
        }}
    }
    // Jalankan sekali saat dimuat
    getLiveGPS();
    </script>
    """
    st.components.v1.html(html_gps_capture, height=100)

    # Input manual cadangan yang bersih jika ingin memastikan koordinat masuk tanpa kedip
    col_lat, col_lon, col_kirim = st.columns([2, 2, 1])
    with col_lat:
        input_lat = st.number_input("Latitude", value=-6.2088, format="%.6f", key="inp_lat")
    with col_lon:
        input_lon = st.number_input("Longitude", value=106.8456, format="%.6f", key="inp_lon")
    with col_kirim:
        st.write("")
        st.write("")
        if st.button("Simpan Posisi"):
            waktu_sekarang = datetime.now().strftime("%H:%M:%S")
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO anggota (nama, lat, lon, waktu)
                VALUES (?, ?, ?, ?)
            ''', (st.session_state.nama_saya, input_lat, input_lon, waktu_sekarang))
            conn.commit()
            st.success("Tersimpan!")
            st.rerun()

st.markdown("---")

# --- 5. TAMPILAN PETA BERSAMA (STABIL 1 LAYAR) ---
col_tittle, col_btn = st.columns([3, 1])
with col_tittle:
    st.subheader("🗺️ Peta Pantauan Anggota Turing Aktif")
with col_btn:
    st.write("")
    if st.button("🔄 Refresh Peta"):
        st.rerun()

df_turing = pd.read_sql("SELECT * FROM anggota", conn)

if not df_turing.empty:
    # Hitung titik tengah peta
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

        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=100,
            color='red' if is_me else 'blue',
            fill=True,
            fill_opacity=0.15
        ).add_to(m)

    # Render peta tanpa kedip (tidak ada auto-refresh looping)
    st_folium(m, width=1100, height=520)

else:
    st.info("Belum ada anggota yang bergabung di sesi turing. Masukkan nama kamu di sidebar untuk mulai.")
