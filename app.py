import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import sqlite3
from datetime import datetime

# Konfigurasi Halaman
st.set_page_config(page_title="Peta Turing Privat", layout="wide")
st.title("📍 Live Tracking Lokasi Grup Turing")

# --- 1. INISIALISASI DATABASE SQLITE ---
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

# --- 2. MANAJEMEN SESI (SESSION STATE) ---
if "nama_saya" not in st.session_state:
    st.session_state.nama_saya = ""
if "sedang_gabung" not in st.session_state:
    st.session_state.sedang_gabung = False

# --- SIDEBAR: KONTROL GABUNG & KELUAR SESI ---
st.sidebar.header("⚙️ Kontrol Sesi Turing")

if not st.session_state.sedang_gabung:
    # TAMPILAN KETIKA BELUM BERGABUNG
    st.sidebar.info("Silakan masukkan nama Anda untuk bergabung ke dalam sesi grup turing.")
    input_nama = st.sidebar.text_input("Nama Anda / Panggilan:")
    
    col_lat, col_lon = st.sidebar.columns(2)
    with col_lat:
        default_lat = st.sidebar.number_input("Latitude Awal", value=-6.2088, format="%.6f")
    with col_lon:
        default_lon = st.sidebar.number_input("Longitude Awal", value=106.8456, format="%.6f")
        
    if st.sidebar.button("🚀 Gabung Sesi Turing", type="primary"):
        if input_nama.strip() != "":
            # Simpan ke session state
            st.session_state.nama_saya = input_nama.strip()
            st.session_state.sedang_gabung = True
            
            # Masukkan ke database
            waktu_sekarang = datetime.now().strftime("%H:%M:%S")
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO anggota (nama, lat, lon, waktu)
                VALUES (?, ?, ?, ?)
            ''', (st.session_state.nama_saya, default_lat, default_lon, waktu_sekarang))
            conn.commit()
            st.rerun()
        else:
            st.sidebar.error("Nama tidak boleh kosong!")

else:
    # TAMPILAN KETIKA SUDAH BERGABUNG (ADA TOMBOL KELUAR)
    st.sidebar.success(f"Anda bergabung sebagai: **{st.session_state.nama_saya}**")
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📡 Update Lokasi Anda")
    up_lat = st.sidebar.number_input("Latitude Terkini", value=-6.2088, format="%.6f")
    up_lon = st.sidebar.number_input("Longitude Terkini", value=106.8456, format="%.6f")
    
    if st.sidebar.button("📍 Kirim Posisi Terbaru"):
        waktu_sekarang = datetime.now().strftime("%H:%M:%S")
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE anggota SET lat = ?, lon = ?, waktu = ? WHERE nama = ?
        ''', (up_lat, up_lon, waktu_sekarang, st.session_state.nama_saya))
        conn.commit()
        st.sidebar.success("Lokasi berhasil diperbarui!")

    st.sidebar.markdown("---")
    
    # TOMBOL KELUAR SESI KHUSUS MILIK YANG BERSANGKUTAN
    if st.sidebar.button("🚪 Keluar Sesi / Akhiri Berbagi", type="secondary"):
        # Hapus dari database agar titik hilang dari peta grup
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota WHERE nama = ?", (st.session_state.nama_saya,))
        conn.commit()
        
        # Reset session state lokal
        st.session_state.sedang_gabung = False
        st.session_state.nama_saya = ""
        st.rerun()

# --- 3. MENU TAMBAHAN ADMIN (OPSIONAL) ---
with st.sidebar.expander("🛠️ Menu Admin / Bantuan"):
    if st.button("Hapus Semua Data (Reset Grup)"):
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anggota")
        conn.commit()
        st.warning("Semua anggota dihapus dari sistem.")
        st.rerun()

# --- 4. TAMPILAN UTAMA: PETA BERSAMA (SATU LAYAR UNTUK SEMUA) ---
st.subheader("🗺️ Peta Pantauan Anggota Turing Aktif")

# Ambil data semua anggota dari database
df_turing = pd.read_sql("SELECT * FROM anggota", conn)

if not df_turing.empty:
    # Info ringkas jumlah anggota online
    st.write(f"Total anggota terpantau aktif di peta saat ini: **{len(df_turing)} orang**")
    
    # Hitung titik tengah peta otomatis
    center_lat = df_turing['lat'].mean()
    center_lon = df_turing['lon'].mean()
    
    m = folium.Map(location=[center_lat, center_lon], zoom_start=13)
    
    # Render semua marker anggota ke dalam 1 peta yang sama
    for idx, row in df_turing.iterrows():
        # Cek apakah ini marker milik pengguna yang sedang membuka aplikasi ini
        is_me = (st.session_state.sedang_gabung and row['nama'].lower() == st.session_state.nama_saya.lower())
        
        warna_marker = 'red' if is_me else 'blue'
        ikon_simbol = 'user' if is_me else 'motorcycle'
        
        popup_html = f"""
        <div style="font-family: sans-serif; width: 150px;">
            <b>{row['nama']}</b> {'(Anda)' if is_me else ''}<br>
            <hr style="margin: 5px 0;">
            <small>Update: {row['waktu']}</small>
        </div>
        """
        
        folium.Marker(
            [row['lat'], row['lon']], 
            popup=folium.Popup(popup_html, max_width=200),
            tooltip=row['nama'],
            icon=folium.Icon(color=warna_marker, icon=ikon_simbol, prefix='fa')
        ).add_to(m)
        
        # Lingkaran area radius untuk mempermanis tampilan
        folium.Circle(
            location=[row['lat'], row['lon']],
            radius=80,
            color='orange' if is_me else 'gray',
            fill=True,
            fill_opacity=0.15
        ).add_to(m)

    # Tampilkan Peta
    st_folium(m, width=1100, height=550)
    
    # Tombol Refresh untuk menarik data posisi terbaru teman lain
    col_ref1, col_ref2 = st.columns([1, 4])
    with col_ref1:
        if st.button("🔄 Refresh Peta"):
            st.rerun()
            
else:
    st.info("Belum ada anggota yang bergabung di sesi turing. Masukkan nama Anda di sidebar untuk memulai.")
