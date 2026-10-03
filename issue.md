Saya ingin membuat aplikasi internal untuk Universitas Sains Indonesia (USI) yang berfungsi sebagai **Moodle LMS Content Checker** untuk semester 2026/2027 Ganjil.

## 1. TUJUAN UTAMA

Aplikasi membaca file Excel daftar kelas/KRS terbaru dari akademik, kemudian:

1. Memfilter kelas yang perlu dicek.
2. Mencocokkan kelas tersebut dengan course di Moodle.
3. Membaca isi course melalui Moodle Web Service API.
4. Mengecek kelengkapan konten LMS untuk Pertemuan 1–14.
5. Mengecek minimal 3 jenis konten:

   * PPT / materi presentasi
   * Video
   * Quiz
6. Menghasilkan report Excel yang mudah dibaca oleh staf akademik.
7. Dapat dijalankan kembali menggunakan Excel terbaru tanpa merusak histori pengecekan sebelumnya.

Aplikasi harus dirancang agar nantinya dapat menangani sekitar 200+ kelas.

---

# 2. MOODLE

URL Moodle:

https://lms2.sains.ac.id

Moodle version:

5.0.8

Web Services sudah aktif.

Token Moodle sudah berhasil dibuat dan **JANGAN pernah meminta user menuliskan token ke dalam source code atau mengirim token ke chat**.

Token harus disimpan melalui environment variable/config lokal yang aman, misalnya:

MOODLE_TOKEN

Contoh konfigurasi:

MOODLE_URL=https://lms2.sains.ac.id
MOODLE_TOKEN=ISI_TOKEN_DI_ENV

Jangan hardcode token.

---

# 3. MOODLE API YANG SUDAH TERBUKTI BERHASIL

API berikut sudah berhasil dites pada Moodle USI:

## API 1

core_course_get_courses_by_field

Digunakan untuk mencari course berdasarkan shortname.

Contoh shortname:

26FA_Psikologi Komunikasi_20261

Response memberikan:

course ID:
245

fullname:
Psikologi Komunikasi - 26FA (Hilda Sri Rahayu,)

shortname:
26FA_Psikologi Komunikasi_20261

## API 2

core_course_get_contents

Digunakan untuk mengambil struktur section dan module/activity dari course.

Contoh request concept:

courseid = 245

Response course yang dites memiliki struktur:

General
section 0

section 1
3 October - 9 October

section 2
10 October - 16 October

section 3
17 October - 23 October

...

section 14
2 January - 8 January

section 15
9 January - 15 January

section 16
16 January - 22 January

Pada course tersebut section 1–16 memiliki modules kosong.

IMPORTANT:

Jangan mengasumsikan section Moodle selalu bernama "Pertemuan 1", "Pertemuan 2", dst.

Pada Moodle USI yang sudah dites, section menggunakan nama rentang tanggal.

Untuk pengecekan perkuliahan, gunakan nomor section sebagai mapping awal:

section 1 → Pertemuan 1
section 2 → Pertemuan 2
...
section 14 → Pertemuan 14

Section 0 = General dan harus diabaikan.

Section 15 dan 16 jangan dianggap sebagai Pertemuan 15/16 karena target semester hanya Pertemuan 1–14.

---

# 4. STRUKTUR SHORTNAME MOODLE

Dari beberapa course yang sudah dicek, format shortname Moodle konsisten:

{KODE_KELAS}*{NAMA_MATAKULIAH}*{KODE_SEMESTER}

Contoh:

26FA_Psikologi Komunikasi_20261

Artinya:

26FA = kode kelas
Psikologi Komunikasi = mata kuliah
20261 = semester 2026/2027 Ganjil

Gunakan shortname ini sebagai mekanisme utama untuk mencari course Moodle.

Jangan menggunakan nama dosen sebagai primary key.

Primary identity/key:

KODE KELAS + MATAKULIAH + SEMESTER

Dosen dapat berubah atau awalnya kosong.

---

# 5. DATA EXCEL INPUT

User memiliki file Excel daftar kelas dari sistem akademik/SIP.

Struktur kolom kurang lebih:

No
Kelas
Matakuliah
SKS
SMT
Jadwal
Dosen Pengajar
Prodi
Peserta / Kuota
Kelas
Ruangan
Kampus
Status
MBKM
LMS

Nama kolom harus dideteksi secara fleksibel karena posisi kolom bisa berubah.

Jangan bergantung pada nomor kolom.

Cari berdasarkan nama/header kolom.

---

# 6. FILTER KELAS

Dari Excel, hanya proses kelas yang memenuhi kriteria:

## A. Bukan kelas online

Kode kelas yang berakhiran:

O

berarti kelas online.

Contoh:

26FAO

harus diabaikan.

Gunakan pengecekan case-insensitive terhadap kode kelas.

Contoh:

26FA → diproses
26FAO → diabaikan

## B. Ruangan

Untuk tahap awal hanya proses:

R2A
R2B
R2C

Jika ruangan selain tiga tersebut, abaikan.

## C. Dosen kosong

Jika Dosen Pengajar kosong:

anggap:

BELUM KRS

Jangan mencari course Moodle berdasarkan data tersebut.

Tetap masukkan ke report sebagai:

Status KRS = BELUM KRS

---

# 7. MASALAH DATA EXCEL YANG HARUS DITANGANI

Excel bersifat snapshot/statis.

Contoh:

Hari ini:

26FB | Psikologi Komunikasi | Dosen kosong

Artinya belum KRS.

Besok Excel terbaru:

26FB | Psikologi Komunikasi | Andi Pratama

Artinya sudah KRS.

Aplikasi harus memperlakukan 26FB sebagai kelas yang sama.

Jangan menggunakan nama dosen sebagai primary key.

Gunakan:

KODE KELAS + MATAKULIAH + SEMESTER

sebagai identity.

Ketika Excel terbaru dimasukkan, data terbaru harus di-refresh tanpa menganggap kelas yang sama sebagai kelas baru.

---

# 8. PENGECEKAN LMS

Untuk setiap kelas yang sudah memiliki dosen:

1. Bentuk shortname Moodle:

{kode_kelas}*{nama_matakuliah}*{20261}

2. Panggil:

core_course_get_courses_by_field

field = shortname

3. Jika ditemukan:

simpan:

Moodle Course ID
Moodle Fullname
Moodle Shortname
Moodle URL

4. Jika tidak ditemukan:

Status LMS:

COURSE TIDAK DITEMUKAN

Jangan dianggap BELUM LENGKAP.

Ini harus menjadi status terpisah.

---

# 9. CEK CONTENT COURSE

Jika course ditemukan:

panggil:

core_course_get_contents

Gunakan hasil section:

section 1 → P1
section 2 → P2
...
section 14 → P14

Abaikan:

section 0
section 15
section 16
dan section lain di luar 1–14.

Untuk setiap P1–P14, periksa modules.

---

# 10. KATEGORI KONTEN

Minimal cek tiga kategori:

## PPT

PPT dianggap tersedia jika terdapat resource/file yang secara jelas merupakan materi presentasi.

Deteksi berdasarkan:

* filename
* module name
* content type
* URL/file metadata jika tersedia

Ekstensi yang harus dipertimbangkan:

.ppt
.pptx

Jika module name mengandung kata seperti:

PPT
PowerPoint
Materi
Slide

juga dapat dipertimbangkan.

Namun prioritaskan bukti dari file/module metadata daripada hanya keyword.

## VIDEO

Video dianggap tersedia jika terdapat aktivitas/resource yang merepresentasikan video.

Pertimbangkan:

* video activity
* URL video
* embedded video
* module name yang mengandung Video
* media/video resource yang tersedia dari API

Jangan hanya mencari kata "video" jika tipe module/API menunjukkan resource video secara jelas.

## QUIZ

Jika:

modname = quiz

maka:

Quiz = tersedia.

---

# 11. STATUS PER PERTEMUAN

Setiap pertemuan harus memiliki status untuk:

PPT
Video
Quiz

Contoh:

P1:
PPT ✅
Video ✅
Quiz ❌

Maka detail:

P1: Quiz

Jika semuanya tersedia:

P1: LENGKAP

Jika semuanya kosong:

P1: PPT, Video, Quiz

---

# 12. STATUS LMS KESELURUHAN

Gunakan status:

## LENGKAP

Jika P1–P14 semuanya memiliki:

PPT
Video
Quiz

## BELUM LENGKAP

Jika course ditemukan tetapi ada satu atau lebih konten yang belum tersedia.

## COURSE TIDAK DITEMUKAN

Jika course Moodle tidak ditemukan.

## BELUM KRS

Jika Dosen Pengajar kosong.

---

# 13. FORMAT DETAIL KEKURANGAN

Buat kolom:

Detail Kekurangan

Contoh:

P2: Video, Quiz | P4: PPT | P7: PPT, Video, Quiz

Jangan menampilkan pertemuan yang lengkap.

Jika semuanya lengkap:

Detail Kekurangan = -

---

# 14. OUTPUT EXCEL

Buat file Excel report dengan minimal sheet:

## Sheet: DATA TERBARU

Kolom:

No
Kelas
Matakuliah
SKS
SMT
Jadwal
Dosen Pengajar
Prodi
Ruangan
Kampus
Status KRS
Moodle Course
Course ID
P1
P2
P3
P4
P5
P6
P7
P8
P9
P10
P11
P12
P13
P14
Status LMS
Detail Kekurangan
Last Check

Setiap P1–P14 dapat berisi:

LENGKAP

atau:

PPT
Video
Quiz

atau kombinasi:

PPT, Quiz

---

# 15. SHEET RIWAYAT

Buat sheet:

RIWAYAT CEK

Setiap kali checker dijalankan, simpan snapshot hasil pengecekan.

Kolom:

Timestamp
Kelas
Matakuliah
Dosen
Course ID
Status LMS
Detail Kekurangan

Contoh:

26/09/2026 20:30
26FA
Psikologi Komunikasi
Hilda Sri Rahayu
245
BELUM LENGKAP
P1: Quiz | P2: Video, Quiz

Kemudian setelah dosen upload:

27/09/2026 10:00
26FA
Psikologi Komunikasi
Hilda Sri Rahayu
245
BELUM LENGKAP
P1: Quiz | P2: Quiz

Dengan demikian progress dapat dilihat dari waktu ke waktu.

---

# 16. JANGAN MENGHAPUS DATA HISTORI

Jika Excel KRS terbaru berubah:

* kelas lama tetap dikenali berdasarkan identity key
* data terbaru menggantikan snapshot pada DATA TERBARU
* RIWAYAT CEK tetap menyimpan pengecekan sebelumnya

Jangan menghapus histori hanya karena Excel terbaru memiliki data berbeda.

---

# 17. HANDLE PERUBAHAN DOSEN

Contoh:

Hari 1:

26FA
Psikologi Komunikasi
Dosen = kosong

Status:

BELUM KRS

Hari 2:

26FA
Psikologi Komunikasi
Dosen = Hilda Sri Rahayu

Maka sistem harus mengenali:

identity key tetap sama.

Status berubah menjadi:

DIPROSES

Kemudian cari course Moodle.

Jangan membuat identity baru hanya karena dosen berubah.

---

# 18. HANDLE COURSE TIDAK DITEMUKAN

Jika Dosen sudah tersedia tetapi shortname Moodle tidak ditemukan:

Status LMS:

COURSE TIDAK DITEMUKAN

Simpan juga alasan/debug:

Expected shortname:
26FA_Psikologi Komunikasi_20261

Ini penting untuk debugging.

---

# 19. ERROR HANDLING

Aplikasi tidak boleh berhenti total jika satu course error.

Contoh:

200 course diproses.

Course ke-37 error.

Tetap lanjut:

38
39
40
dst.

Simpan error ke kolom:

Error

dan lanjutkan proses.

Contoh:

API ERROR
TIMEOUT
COURSE NOT FOUND
INVALID RESPONSE

Tambahkan retry untuk request API yang gagal sementara.

Gunakan rate limiting/concurrency yang aman agar tidak membebani Moodle.

---

# 20. CACHING

Karena jumlah course sekitar 200+, jangan melakukan request yang tidak perlu.

Gunakan cache untuk:

* shortname → course ID
* course ID → course contents

Namun cache harus bisa di-refresh.

Sediakan mode:

FULL REFRESH

dan:

NORMAL REFRESH

Normal refresh boleh menggunakan cache jika sesuai kebutuhan.

Full refresh memanggil Moodle API kembali.

---

# 21. KEAMANAN

Token Moodle:

* jangan hardcode
* jangan ditulis ke Excel
* jangan ditulis ke log
* jangan ditampilkan di UI
* jangan dikirim ke console output
* gunakan `.env`

Tambahkan `.env` ke `.gitignore`.

Sediakan:

`.env.example`

dengan:

MOODLE_URL=https://lms2.sains.ac.id
MOODLE_TOKEN=

---

# 22. LOGGING

Buat log sederhana:

* waktu mulai
* jumlah row Excel
* jumlah kelas setelah filter
* jumlah BELUM KRS
* jumlah course ditemukan
* jumlah course tidak ditemukan
* jumlah course LENGKAP
* jumlah course BELUM LENGKAP
* jumlah error

Contoh:

Total Excel rows: 350
Filtered classes: 218
Belum KRS: 24
Course ditemukan: 184
Course tidak ditemukan: 10
LMS lengkap: 65
LMS belum lengkap: 119
Error: 0

---

# 23. USER INTERFACE

Untuk versi awal tidak perlu UI kompleks.

Boleh menggunakan:

* Python CLI
  atau
* aplikasi desktop/web sederhana

Prioritas utama:

FUNCTIONALITY > DESIGN

Workflow ideal:

1. User pilih/upload Excel terbaru.
2. Klik Start Checking.
3. Aplikasi membaca Excel.
4. Filter kelas.
5. Connect Moodle API.
6. Cari course.
7. Cek P1–P14.
8. Tampilkan progress.
9. Generate Excel report.
10. Simpan histori.

---

# 24. PROGRESS

Karena 200+ course dapat memakan waktu, tampilkan progress:

Checking 45 / 218

atau progress bar:

████████░░░░ 45%

Tambahkan nama kelas yang sedang diproses.

---

# 25. EXCEL FORMATTING

Output Excel harus nyaman dibaca.

Gunakan:

* freeze header
* autofilter
* column width otomatis
* header bold
* wrap text
* alignment yang sesuai
* format tanggal/waktu
* conditional formatting untuk status

Gunakan warna secukupnya dan jangan membuat spreadsheet terlalu ramai.

Status:

LENGKAP
BELUM LENGKAP
COURSE TIDAK DITEMUKAN
BELUM KRS

harus mudah dibedakan secara visual.

---

# 26. ARSITEKTUR CODE

Pisahkan fungsi agar mudah dikembangkan.

Contoh:

config.py
moodle_api.py
excel_reader.py
course_matcher.py
content_checker.py
history.py
report_generator.py
main.py

Atau struktur yang setara jika framework yang dipilih berbeda.

Jangan membuat semua logic dalam satu file.

---

# 27. API CLIENT

Buat class/service:

MoodleClient

dengan method minimal:

get_courses_by_shortname(shortname)

get_course_contents(course_id)

request()

API endpoint:

/webservice/rest/server.php

Parameter umum:

wstoken
wsfunction
moodlewsrestformat=json

Gunakan POST jika lebih aman/tepat untuk request API.

Jangan menampilkan token pada exception/error.

---

# 28. NORMALISASI DATA

Sebelum matching:

trim whitespace.

Normalisasi:

* kode kelas → uppercase
* nama matakuliah → trim
* dosen → trim
* ruangan → uppercase

Tetapi jangan mengubah nama mata kuliah secara agresif karena nama tersebut digunakan dalam shortname Moodle.

Jika diperlukan, buat fungsi normalisasi khusus yang hanya membersihkan whitespace berlebih.

---

# 29. IMPORTANT: JANGAN ASUMSI STRUKTUR YANG BELUM DITES

Kita sudah membuktikan:

core_course_get_courses_by_field → BERHASIL

core_course_get_contents → BERHASIL

Tetapi kita belum selesai memverifikasi seluruh variasi module Moodle.

Karena itu:

* jangan hardcode satu tipe resource saja
* buat detector PPT/Video/Quiz modular
* simpan raw module information jika diperlukan untuk debugging
* jika sebuah module tidak bisa dikategorikan, masukkan ke log/debug, bukan langsung dianggap PPT/Video

---

# 30. TESTING

Sebelum menjalankan 200+ kelas, buat test menggunakan:

1. Course yang tidak ditemukan.
2. Course yang ditemukan tetapi kosong.
3. Course yang memiliki PPT.
4. Course yang memiliki Video.
5. Course yang memiliki Quiz.
6. Course yang memiliki ketiganya.
7. Excel dengan dosen kosong.
8. Excel dengan dosen yang sudah terisi.
9. Perubahan dosen dari kosong menjadi terisi.
10. Excel terbaru yang memiliki kelas sama seperti sebelumnya.

Buat unit test untuk fungsi:

build_shortname()
filter_classes()
match_course()
detect_ppt()
detect_video()
detect_quiz()
calculate_meeting_status()
calculate_overall_status()

---

# 31. JANGAN LANGSUNG MEMPROSES 200 KELAS

Implementasikan bertahap.

PHASE 1:
Excel reader + filter.

PHASE 2:
Moodle course lookup.

PHASE 3:
Course contents parser.

PHASE 4:
PPT/Video/Quiz detector.

PHASE 5:
Excel report.

PHASE 6:
History.

PHASE 7:
Caching + retry + performance.

PHASE 8:
UI/progress.

Setiap phase harus dites sebelum lanjut.

---

# 32. HAL YANG HARUS DILAKUKAN CODING AGENT

Sebelum coding:

1. Inspect repository/project yang tersedia.
2. Identifikasi bahasa/framework yang paling sesuai.
3. Jangan mengubah file yang tidak relevan.
4. Jika project kosong, buat struktur project yang bersih.
5. Jelaskan dependency yang dibutuhkan.
6. Buat `.env.example`.
7. Buat README dengan cara menjalankan aplikasi.

Jika ada bagian spesifikasi yang ambigu, jangan mengarang perilaku Moodle.

Gunakan API response nyata yang diberikan di prompt sebagai referensi.

---

# 33. PRIORITAS

Prioritas sistem:

1. Akurasi pencocokan kelas ↔ Moodle.
2. Akurasi deteksi PPT/Video/Quiz.
3. Tidak kehilangan histori.
4. Aman terhadap Excel terbaru.
5. Error handling.
6. Performance.
7. UI.

Jangan mengorbankan akurasi demi UI.

---

# 34. OUTPUT YANG SAYA INGINKAN DARI CODING AGENT

Mulai dengan:

1. Analisis struktur project.
2. Buat architecture plan singkat.
3. Implementasikan PHASE 1.
4. Jalankan test.
5. Tampilkan hasil test.
6. Setelah PHASE 1 berhasil, lanjut PHASE 2.
7. Jangan langsung membuat seluruh sistem tanpa testing bertahap.

Pada setiap phase, berikan:

* file yang dibuat/diubah
* alasan perubahan
* cara menjalankan
* hasil test
* error jika ada

Target akhirnya adalah aplikasi yang bisa digunakan staf akademik USI untuk mengecek kelengkapan LMS 200+ kelas secara otomatis dari Excel KRS terbaru.
