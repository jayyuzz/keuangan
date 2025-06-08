from flask import Flask, render_template, request, redirect, url_for, flash, Response
import pdfkit
import sqlite3
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Ganti dengan kunci rahasia yang aman

# Fungsi untuk menghubungkan ke database SQLite
def get_db_connection():
    conn = sqlite3.connect('keuangan.db')
    conn.row_factory = sqlite3.Row  # Mengembalikan hasil sebagai dictionary
    return conn

# Inisialisasi database dan tabel
def init_db():
    conn = get_db_connection()
    # Tabel pengeluaran
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pengeluaran (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kategori TEXT NOT NULL,
            jumlah REAL NOT NULL,
            tanggal TEXT NOT NULL
        )
    ''')
    # Tabel pemasukan
    conn.execute('''
        CREATE TABLE IF NOT EXISTS pemasukan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keterangan TEXT NOT NULL,
            jumlah REAL NOT NULL,
            tanggal TEXT NOT NULL
        )
    ''')
    # Tabel saldo_harian
    conn.execute('''
        CREATE TABLE IF NOT EXISTS saldo_harian (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tanggal TEXT NOT NULL,
            saldo REAL NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/')
def index():
    """
    Halaman utama yang menampilkan daftar pemasukan, pengeluaran, dan total saldo.
    """
    conn = get_db_connection()
    pengeluaran = conn.execute('SELECT * FROM pengeluaran').fetchall()
    pemasukan = conn.execute('SELECT * FROM pemasukan').fetchall()

    total_pengeluaran = sum(item['jumlah'] for item in pengeluaran)
    total_pemasukan = sum(item['jumlah'] for item in pemasukan)
    saldo = total_pemasukan - total_pengeluaran

    # Simpan saldo akhir ke dalam tabel saldo_harian
    tanggal_hari_ini = datetime.now().strftime('%Y-%m-%d')
    conn.execute('INSERT OR IGNORE INTO saldo_harian (tanggal, saldo) VALUES (?, ?)', (tanggal_hari_ini, saldo))
    conn.commit()

    # Ambil saldo dari hari sebelumnya
    saldo_hari_sebelumnya = conn.execute('SELECT saldo FROM saldo_harian WHERE tanggal < ? ORDER BY tanggal DESC LIMIT 1', 
                                          (tanggal_hari_ini,)).fetchone()
    conn.close()

    return render_template('index.html', pengeluaran=pengeluaran, pemasukan=pemasukan, 
                           total_pengeluaran=total_pengeluaran, total_pemasukan=total_pemasukan, 
                           saldo=saldo, saldo_hari_sebelumnya=saldo_hari_sebelumnya)

@app.route('/tambah_pengeluaran', methods=['POST'])
def tambah_pengeluaran():
    """
    Menangani penambahan pengeluaran dari form.
    """
    kategori = request.form.get('kategori')
    try:
        jumlah = float(request.form.get('jumlah'))
        if jumlah < 0:
            flash("Jumlah pengeluaran tidak boleh negatif.", "error")
            return redirect(url_for('index'))
        
        tanggal = request.form.get('tanggal')  # Ambil tanggal dari form
        conn = get_db_connection()
        conn.execute('INSERT INTO pengeluaran (kategori, jumlah, tanggal) VALUES (?, ?, ?)', (kategori, jumlah, tanggal))
        conn.commit()
        conn.close()
        flash("Pengeluaran berhasil ditambahkan!", "success")
    except ValueError:
        flash("Masukkan jumlah yang valid.", "error")
    
    return redirect(url_for('index'))

@app.route('/tambah_pemasukan', methods=['POST'])
def tambah_pemasukan():
    """
    Menangani penambahan pemasukan dari form.
    """
    keterangan = request.form.get('keterangan')
    try:
        jumlah = float(request.form.get('jumlah'))
        if jumlah < 0:
            flash("Jumlah pemasukan tidak boleh negatif.", "error")
            return redirect(url_for('index'))
        
        tanggal = request.form.get('tanggal')  # Ambil tanggal dari form
        conn = get_db_connection()
        conn.execute('INSERT INTO pemasukan (keterangan, jumlah, tanggal) VALUES (?, ?, ?)', (keterangan, jumlah, tanggal))
        conn.commit()
        conn.close()
        flash("Pemasukan berhasil ditambahkan!", "success")
    except ValueError:
        flash("Masukkan jumlah yang valid.", "error")
    
    return redirect(url_for('index'))

@app.route('/export_pdf', methods=['POST'])
def export_pdf():
    """
    Mengekspor laporan ke PDF berdasarkan range tanggal.
    """
    # Ambil tanggal dari form
    start_date = request.form.get('start_date')
    end_date = request.form.get('end_date')

    # Validasi input tanggal
    if not start_date or not end_date:
        flash("Harap masukkan range tanggal yang valid.", "danger")
        return redirect(url_for('index'))

    conn = get_db_connection()

    # Ambil data pemasukan berdasarkan range tanggal
    pemasukan = conn.execute('''
        SELECT * FROM pemasukan
        WHERE tanggal BETWEEN ? AND ?
    ''', (start_date, end_date)).fetchall()

    # Ambil data pengeluaran berdasarkan range tanggal
    pengeluaran = conn.execute('''
        SELECT * FROM pengeluaran
        WHERE tanggal BETWEEN ? AND ?
    ''', (start_date, end_date)).fetchall()

    # Hitung total pemasukan dan pengeluaran
    total_pemasukan = sum(item['jumlah'] for item in pemasukan)
    total_pengeluaran = sum(item['jumlah'] for item in pengeluaran)

    # Hitung saldo akhir
    saldo_akhir = total_pemasukan - total_pengeluaran

    conn.close()

    # Render template HTML untuk PDF
    rendered = render_template(
        'pdf_template.html',
        pemasukan=pemasukan,
        pengeluaran=pengeluaran,
        start_date=start_date,
        end_date=end_date,
        total_pemasukan=total_pemasukan,
        total_pengeluaran=total_pengeluaran,
        saldo_akhir=saldo_akhir
    )

    # Konfigurasi pdfkit dengan path ke wkhtmltopdf jika diperlukan
    config = pdfkit.configuration(wkhtmltopdf='C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe')  # Ganti dengan path yang sesuai

    # Konversi HTML ke PDF
    pdf = pdfkit.from_string(rendered, False, configuration=config)

    # Kirim file PDF sebagai respons
    response = Response(pdf, content_type='application/pdf')
    response.headers['Content-Disposition'] = f'inline; filename=laporan_{start_date}_to_{end_date}.pdf'
    return response


if __name__ == "__main__":
    init_db()  # Inisialisasi database saat aplikasi dijalankan
    app.run(debug=True)
