# Soal Teori UAS : Pub_Sub Log Aggregator
**Sistem Paralel dan Terdistribusi**
# Pub-Sub Log Aggregator dengan Idempotent Consumer dan Kontrol Konkurensi

Nama: Yunnifa Nur Lailli
Mata Kuliah: Sistem Terdistribusi
Jenis Tugas: UTS Take-Home (Individu)
Bahasa Implementasi: Python
Buku Utama: Tanenbaum & Van Steen – Distributed Systems (Bab 1–13)
---
## T1 — Karakteristik Sistem Terdistribusi dan Trade-off Desain
(Bab 1 – Introduction)

**Soal:**  
Jelaskan karakteristik utama sistem terdistribusi dan trade-off yang umum pada desain Pub-Sub log aggregator.

**Jawaban:**  
Sistem terdistribusi merupakan sistem yang tersusun dari beberapa komputer yang saling terhubung melalui jaringan dan bekerja bersama seolah-olah sebagai satu sistem terpadu. Walaupun dari sisi pengguna sistem tampak sederhana, pada kenyataannya setiap komputer bekerja secara independen dan hanya dapat berkomunikasi melalui pertukaran pesan (Tanenbaum & Van Steen, 2023). Perbedaan ini membuat sistem terdistribusi memiliki tantangan khas dibanding sistem terpusat.

Salah satu karakteristik utama sistem terdistribusi adalah **konkurensi**, yaitu banyak proses berjalan secara bersamaan. Dalam log aggregator, kondisi ini terlihat ketika banyak publisher mengirim event hampir pada waktu yang sama. Jika tidak dikelola dengan baik, konkurensi dapat menyebabkan konflik data atau inkonsistensi hasil pemrosesan. Selain itu, sistem terdistribusi tidak memiliki **jam global**, sehingga urutan kejadian tidak selalu dapat ditentukan secara absolut. Perbedaan waktu antar mesin dan latency jaringan membuat timestamp dari berbagai sumber tidak selalu sejalan.

Karakteristik lain yang penting adalah **kegagalan independen** (*partial failures*). Setiap komponen dapat gagal tanpa mematikan sistem secara keseluruhan. Bahkan, sering kali sulit membedakan apakah sebuah komponen benar-benar gagal atau hanya mengalami keterlambatan jaringan.

Trade-off utama pada desain Pub-Sub log aggregator muncul dari kondisi tersebut. Untuk menjaga keandalan, sistem menerima mekanisme retry yang berpotensi menghasilkan event duplikat. Daripada mengejar jaminan **exactly-once** yang kompleks dan mahal, sistem ini memilih pendekatan lebih realistis dengan menerima duplikasi dan mengelolanya melalui **idempotency** dan **deduplication**.

---

## T2 — Arsitektur Client-Server vs Publish-Subscribe
(Bab 2 – Architectures)

**Soal:**  
Kapan memilih arsitektur publish–subscribe dibanding client–server? Alasan teknis.

**Jawaban:**  
Arsitektur **client-server** bekerja dengan pola komunikasi langsung, di mana client harus mengetahui alamat server dan berinteraksi secara sinkron. Pendekatan ini relatif mudah dipahami dan diimplementasikan, namun memiliki keterbatasan ketika sistem berkembang atau jumlah client meningkat. Ketergantungan langsung antara client dan server membuat sistem kurang fleksibel terhadap perubahan.

Sebaliknya, arsitektur **publish-subscribe** memisahkan pengirim dan penerima event. Publisher hanya mengirim event ke sistem tanpa mengetahui siapa yang akan menerimanya. Subscriber cukup berlangganan pada topik tertentu, sementara middleware bertugas mengatur distribusi event. Coulouris dkk. menjelaskan bahwa pola ini memberikan pemisahan yang jelas antara pengirim dan penerima, baik dari sisi ruang maupun waktu, sehingga sistem menjadi lebih longgar keterikatannya (*loose coupling*) (Coulouris et al., 2012).

Dalam konteks log aggregator, publish-subscribe lebih tepat digunakan karena log berasal dari banyak sumber dan dapat diproses oleh berbagai komponen dengan kebutuhan berbeda. Implementasi ini juga memanfaatkan **location transparency** melalui Docker DNS (service discovery), sehingga publisher tidak perlu mengetahui lokasi fisik aggregator/storage. Pendekatan ini membuat sistem lebih mudah dikembangkan, dipelihara, dan diskalakan.

---

## T3 — Delivery Semantics dan Idempotent Consumer
(Bab 3 – Processes and Communication)

**Soal:**  
At-least-once vs exactly-once delivery; peran idempotent consumer.

**Jawaban:**  
**At-least-once delivery** menjamin bahwa sebuah event akan dikirim setidaknya satu kali, namun tidak menutup kemungkinan event yang sama diterima lebih dari sekali. Pendekatan ini banyak digunakan karena sederhana dan cukup andal menghadapi jaringan tidak stabil. Sebaliknya, **exactly-once delivery** berusaha memastikan event hanya diproses satu kali, tetapi implementasinya jauh lebih kompleks dan mahal.

Dalam praktik sistem terdistribusi, pengirim tidak dapat memastikan apakah sebuah event benar-benar gagal diproses atau hanya mengalami keterlambatan. Karena itu, retry menjadi mekanisme yang tidak bisa dihindari. Coulouris dkk. menekankan bahwa ketidakmampuan membedakan antara pesan hilang dan pesan terlambat merupakan salah satu alasan utama mengapa jaminan exactly-once sulit diwujudkan secara praktis (Coulouris et al., 2012).

**Idempotent consumer** menjadi solusi yang lebih realistis. Consumer dirancang agar pemrosesan event yang sama tidak mengubah hasil akhir sistem setelah pemrosesan pertama berhasil. Pada sistem ini, meskipun event dengan identifier yang sama diterima berkali-kali akibat retry, penulisan ke database hanya terjadi sekali melalui deduplication store yang persisten. Dengan pendekatan ini, at-least-once delivery dapat digunakan secara aman tanpa menimbulkan inkonsistensi.

---

## T4 — Penamaan Topic dan Event ID
(Bab 4 – Naming)

**Soal:**  
Skema penamaan topic dan event_id (unik, collision-resistant) untuk dedup.

**Jawaban:**  
Dalam sistem terdistribusi, penamaan berperan penting untuk memastikan setiap entitas dapat dikenali secara konsisten. Tanenbaum dan Van Steen menekankan bahwa identifier sebaiknya bersifat **unik**, **stabil**, dan tidak bergantung pada lokasi fisik sistem, sehingga tetap valid walau komponen berpindah atau diskalakan (Tanenbaum & Van Steen, 2023). Prinsip ini menjadi dasar perancangan skema penamaan pada sistem log aggregator.

Sistem ini menggunakan kombinasi **topic** dan **event_id** sebagai penanda unik setiap event. Topic digunakan untuk mengelompokkan event berdasarkan domain log, sedangkan event_id berfungsi sebagai identifier yang membedakan satu event dengan event lainnya. Dengan pola ini, event dengan payload atau timestamp yang mirip tetap dapat dibedakan secara deterministik.

Dampaknya terhadap deduplication sangat signifikan. Ketika event dengan kombinasi `(topic, event_id)` yang sama diterima kembali, sistem dapat langsung mengenalinya sebagai duplikat tanpa perlu membandingkan isi payload. Proses deduplikasi menjadi lebih sederhana, efisien, dan mendukung pemrosesan idempotent. Pada implementasi, pasangan `(topic, event_id)` dipaksakan unik di database melalui **UNIQUE constraint**, sehingga dedup juga aman terhadap kondisi konkurensi.

---

## T5 — Waktu dan Ordering Event
(Bab 5 – Time and Ordering)

**Soal:**  
Ordering praktis (timestamp + monotonic counter); batasan dan dampaknya.

**Jawaban:**  
Masalah waktu dan urutan kejadian menjadi tantangan dalam sistem terdistribusi karena tidak adanya jam global. **Total ordering** memungkinkan semua event diproses dalam urutan yang sama, tetapi membutuhkan koordinasi tambahan yang mahal dan dapat menurunkan performa sistem.

Pada sistem log aggregator, total ordering tidak selalu diperlukan. Fokus utama sistem adalah memastikan seluruh event tercatat dengan benar dan konsisten, bukan menjaga urutan global yang ketat. Karena itu, sistem ini menggunakan pendekatan praktis dengan mengandalkan timestamp berbasis **ISO8601 (UTC)** dari masing-masing source, dan memvalidasi formatnya secara ketat di layer input agar konsisten.

Pendekatan ini cukup untuk kebutuhan analisis dan observabilitas log. Namun, sistem menyadari keterbatasan: perbedaan waktu antar mesin (*clock drift*) dapat menyebabkan ordering tidak mencerminkan urutan kejadian sebenarnya. Trade-off ini diterima demi menjaga performa, kesederhanaan, dan fokus pada konsistensi akhir melalui idempotency + deduplication.

---

## T6 — Failure Modes dan Strategi Mitigasi
(Bab 6 – Fault Tolerance)

**Soal:**  
Failure modes dan mitigasi (retry, backoff, durable dedup store, crash recovery).

**Jawaban:**  
Dalam sistem terdistribusi, kegagalan merupakan kondisi yang harus diantisipasi sejak awal. Event dapat dikirim ulang, diproses tidak berurutan, atau sistem dapat mengalami crash sewaktu-waktu. Coulouris dkk. menyatakan bahwa kegagalan parsial merupakan karakteristik normal dari sistem terdistribusi (Coulouris et al., 2012).

Untuk mengatasi **duplikasi** akibat retry, sistem ini menerapkan deduplication yang disimpan secara persisten di **PostgreSQL**. Dedup store ini berada pada **Docker named volume**, sehingga status deduplikasi tetap tersedia meskipun container direstart atau direcreate. Selain itu, pemrosesan event dibuat **idempotent** agar retry tidak menimbulkan efek samping tambahan.

Untuk **out-of-order**, sistem tidak memaksakan total ordering karena biaya koordinasinya tinggi. Timestamp ISO8601 cukup untuk ordering praktis saat query/analisis, meskipun tidak menjamin urutan absolut.

Untuk **crash**, sistem mengandalkan durabilitas database dan inisialisasi otomatis (init_db) sehingga setelah restart sistem tetap siap memproses event tanpa kehilangan konsistensi. Dengan kombinasi ini, sistem dapat pulih cepat dan tetap menjaga state akhir yang benar.

---

## T7 — Eventual Consistency
(Bab 7 – Consistency and Replication)

**Soal:**  
Eventual consistency pada aggregator; peran idempotency + dedup.

**Jawaban:**  
**Eventual consistency** menggambarkan kondisi di mana sistem tidak selalu konsisten setiap saat, tetapi akan mencapai konsistensi pada akhirnya setelah semua update/propagasi selesai. Model ini umum pada sistem terdistribusi karena lebih toleran terhadap kegagalan dan partisi jaringan dibanding konsistensi kuat (Tanenbaum & Van Steen, 2023).

Dalam sistem log aggregator, eventual consistency berarti database pada akhirnya hanya akan berisi event unik. Meskipun event diterima berulang kali (duplikasi) atau dalam urutan berbeda (out-of-order), state akhir sistem tetap benar.

**Idempotency** memastikan bahwa pemrosesan ulang event yang sama tidak mengubah hasil akhir sistem setelah pemrosesan pertama. **Deduplication** mencegah event duplikat tersimpan lebih dari sekali melalui kunci unik `(topic, event_id)` di PostgreSQL. Dengan demikian, sistem dapat menerima at-least-once delivery tanpa menghasilkan inkonsistensi, dan pada akhirnya mencapai state yang sama seolah-olah setiap event hanya diproses satu kali.

---

## T8 — Desain Transaksi: ACID, Isolation Level, dan Strategi Menghindari Lost Update
(Bab 8 – Transactions)  **(Fokus UAS)**

**Soal:**  
Desain transaksi: ACID, isolation level, dan strategi menghindari lost-update.

**Jawaban:**  
Transaksi diperlukan untuk menjaga integritas data ketika sistem memproses banyak event secara paralel. Konsep **ACID** memberikan kerangka: *atomicity* memastikan serangkaian operasi database (misalnya insert event + update statistik) diperlakukan sebagai satu kesatuan; *consistency* memastikan constraint dan aturan schema tetap valid; *isolation* membatasi efek interleaving transaksi; dan *durability* memastikan data tetap tersimpan setelah commit walaupun terjadi crash.

Pada sistem ini, pemrosesan event (termasuk batch) dibungkus dalam transaksi database melalui session/transaction scope (`get_db_session`). Untuk dedup, sistem menggunakan pola penulisan idempotent `INSERT ... ON CONFLICT DO NOTHING` sehingga keputusan “event baru vs duplikat” terjadi atomik di sisi database, bukan di aplikasi.

Risiko **lost update** terutama terjadi pada tabel statistik ketika beberapa worker meng-update counter pada waktu bersamaan. Untuk mencegahnya, sistem tidak melakukan read-modify-write di Python. Sebaliknya, sistem memakai **atomic increments** melalui query SQL mentah, misalnya `UPDATE stats SET received = received + :val`, sehingga database melakukan increment secara aman terhadap konkurensi.

Isolation level yang dipilih adalah **READ COMMITTED** untuk menyeimbangkan performa dan konsistensi. Dengan UNIQUE constraint dan operasi update atomik, sistem tetap benar untuk kebutuhan UAS tanpa overhead isolation lebih tinggi.

---

## T9 — Kontrol Konkurensi: Locking/Unique Constraints/Upsert; Idempotent Write Pattern
(Bab 9 – Concurrency Control)  **(Fokus UAS)**

**Soal:**  
Kontrol konkurensi: locking/unique constraints/upsert; idempotent write pattern.

**Jawaban:**  
Kontrol konkurensi dibutuhkan karena aggregator dapat menerima request paralel dan consumer dapat berjalan multi-thread/worker. Risiko utamanya adalah **race condition** yang menyebabkan event sama diproses dua kali (*double-process*) atau statistik menjadi tidak akurat akibat update yang saling menimpa.

Mekanisme utama sistem ini adalah **strong deduplication** berbasis database: tabel `processed_events` memiliki **UNIQUE constraint** pada pasangan `(topic, event_id)`. Saat dua transaksi bersamaan mencoba menyimpan event yang sama, database hanya mengizinkan satu insert berhasil. Transaksi lain akan mengalami konflik dan ditangani melalui pola `INSERT ... ON CONFLICT DO NOTHING`. Ini membuat operasi insert bersifat **idempotent** dan aman dari race condition, karena keputusan konflik ditangani di level DB secara atomik (bukan check-then-insert di aplikasi yang rentan TOCTOU).

Untuk statistik, sistem memakai **atomic increments** seperti `UPDATE stats SET duplicate_dropped = duplicate_dropped + 1` sehingga update tidak saling menimpa. Pendekatan ini mencegah lost updates walaupun banyak worker meng-update counter secara bersamaan.

Selain itu, penggunaan `scoped_session` (SQLAlchemy) memastikan isolasi session per thread sehingga state transaksi tidak tercampur antar worker. Kombinasi UNIQUE constraint + ON CONFLICT + atomic increments membuktikan sistem bebas race dan konsisten di bawah beban.

---

## T10 — Orkestrasi Compose, Keamanan Jaringan Lokal, Persistensi, dan Observability
(Bab 10–13)

**Soal:**  
Orkestrasi Compose, keamanan jaringan lokal, persistensi (volume), observability.

**Jawaban:**  
Docker Compose digunakan untuk mengorkestrasi sistem menjadi beberapa layanan terpisah: `aggregator`, `publisher`, `storage` (PostgreSQL), dan `broker` (Redis). Pola multi-service ini mencerminkan arsitektur sistem terdistribusi modern dan memudahkan deployment maupun pengujian end-to-end. Komunikasi antarlayanan memanfaatkan **service discovery** bawaan Docker melalui DNS internal (hostname service), sehingga tidak ada dependensi pada IP statis.

Dari sisi keamanan dan ketentuan tugas, sistem berjalan pada **jaringan lokal Compose** tanpa ketergantungan layanan eksternal publik. Service seperti PostgreSQL dan Redis tetap internal, sementara port aggregator diekspos hanya untuk demo lokal.

Persistensi data dijaga melalui **Docker named volumes** pada PostgreSQL. Dengan demikian, data event dan state deduplikasi tetap bertahan meskipun container dihentikan, dihapus, lalu dibuat ulang (recreate). Ini penting agar crash recovery tetap benar: event yang sudah diproses tidak diproses ulang setelah restart.

Untuk observability, sistem menyediakan endpoint `GET /stats` yang menampilkan metrik `received`, `unique_processed`, dan `duplicate_dropped`, serta endpoint `GET /health` untuk memeriksa konektivitas database. Kombinasi ini dapat membuat sistem mudah dipantau dan dibuktikan .

---
Daftar Pustaka

Tanenbaum, A. S., & Van Steen, M. (2023). Distributed systems (4th ed.). Maarten van Steen.

Coulouris, G., Dollimore, J., Kindberg, T., & Blair, G. (2012). Distributed systems: Concepts and design (5th ed.). Addison-Wesley.

---

## Ringkasan Sistem
Sistem ini merupakan implementasi **Pub-Sub Log Aggregator** yang berjalan sebagai **multi-service** di Docker Compose: `publisher` (generator event), `aggregator` (FastAPI API + consumer internal), `storage` (PostgreSQL persisten), dan `broker` (Redis internal). Publisher mengirim event/log ke endpoint `POST /publish` (mendukung single maupun batch), aggregator memvalidasi skema event menggunakan **Pydantic V2** (field minimal: `topic`, `event_id`, `timestamp`, `source`, `payload`), lalu memproses event secara **idempotent** dan melakukan **deduplikasi kuat** menggunakan pasangan kunci unik `(topic, event_id)` pada PostgreSQL.

Sistem didesain untuk **at-least-once delivery**, artinya publisher dapat mengirim ulang event yang sama ketika terjadi retry jaringan. Untuk mencegah efek samping ganda, aggregator menerapkan pola penulisan idempotent `INSERT ... ON CONFLICT DO NOTHING` dengan **UNIQUE constraint** pada `(topic, event_id)` sehingga hanya event unik yang tersimpan. Selain itu, pembaruan statistik `received`, `unique_processed`, dan `duplicate_dropped` dilakukan secara atomik dengan query `UPDATE stats SET received = received + :val` untuk mencegah **lost update** saat pemrosesan konkuren. Persistensi data dijamin oleh **Docker named volumes** pada PostgreSQL, sehingga data tetap ada walaupun container direcreate.

---

**Teknologi Stack:**
- Python 3.11.14 dengan FastAPI 
- PostgreSQL 16 
- Redis 7 
- Docker Compose untuk orchestration

**Hasil Performance:**
- Memproses 20,000+ events 
- Throughput: ~477 events/sec (38.29 sec)
- Duplication rate: 30%
- Zero race conditions (verified dengan 31 tests)

---

## ARSITEKTUR SISTEM
# REPORT UAS — Pub-Sub Distributed Log Aggregator
**Mata Kuliah:** Sistem Terdistribusi (Sistem Paralel dan Terdistribusi)  
**Jenis:** UAS Take-Home (Individu)  
**Nama:** Yunnifa Nur Lailli  
**Bahasa Implementasi:** Python (FastAPI)  
**Orkestrasi:** Docker Compose (multi-service)  
**Storage:** PostgreSQL 16 (persistent named volume)  
**Broker:** Redis 7 (internal service)  
**Tema:** Pub-Sub Log Aggregator terdistribusi dengan Idempotent Consumer, Strong Deduplication, dan Transaksi/Kontrol Konkurensi

---

## Ringkasan Sistem
Sistem ini mengimplementasikan **Pub-Sub Log Aggregator** yang menerima event/log dari banyak publisher melalui endpoint `POST /publish` (mendukung single maupun batch). Event divalidasi menggunakan Pydantic (schema minimal: `topic`, `event_id`, `timestamp`, `source`, `payload`), kemudian diproses oleh consumer internal secara **idempotent** dan **strongly deduplicated** berdasarkan pasangan kunci unik `(topic, event_id)` pada PostgreSQL.

Desain sistem mengadopsi **at-least-once delivery** (publisher dapat melakukan retry dengan exponential backoff) sehingga event duplikat merupakan kondisi normal. Untuk menjaga konsistensi akhir (*eventual consistency*), aggregator menolak side-effect ganda melalui:
- **UNIQUE constraint** pada `(topic, event_id)` dan pola **idempotent write** `INSERT ... ON CONFLICT DO NOTHING`.
- Update statistik `received`, `unique_processed`, `duplicate_dropped` dilakukan dengan **atomic increments** `UPDATE ... SET count = count + 1` untuk mencegah *lost update* saat beban tinggi.

Sistem berjalan sebagai arsitektur multi-service di jaringan internal Docker Compose (tanpa ketergantungan layanan eksternal publik). Data tetap bertahan meskipun container direcreate karena menggunakan **named volumes** pada PostgreSQL.

---

## Arsitektur Sistem (High-Level)

```text
+-------------------+     HTTP POST /publish      +---------------------------+
| Publisher Service | --------------------------> | Aggregator (FastAPI)      |
| (event generator) |                             | - Validator (Pydantic)    |
| - 25k events      |                             | - Consumer (idempotent)   |
| - 30% duplicate   |                             | - Stats + Observability   |
+---------+---------+                             +------------+--------------+
          |                                                      |
          | (optional async decouple)                             | SQL (Tx)
          v                                                      v
+-------------------+                                    +----------------------+
| Redis Broker      |                                    | PostgreSQL Storage   |
| (internal only)   |                                    | - processed_events   |
+-------------------+                                    | - stats (atomic)     |
                                                         +----------+-----------+
                                                                    |
                                                                    v
                                                          +----------------------+
                                                          | GET /events, /stats  |
                                                          +----------------------+

```

Komponen Utama Sistem

Publisher: Simulator klien yang mengirimkan log event melalui protokol HTTP POST. Pada skenario uji UAS, publisher dikonfigurasi untuk mengirim ulang event yang sama guna mensimulasikan kegagalan jaringan (at-least-once delivery semantics).

FastAPI Aggregator: Layanan inti yang berfungsi menerima request, mengelola validasi skema secara asinkron, dan mengoordinasikan transaksi database agar tetap konsisten di bawah beban kerja tinggi.

Event Validator (Pydantic V2): Menggunakan standar Pydantic terbaru untuk memastikan setiap field minimal (topic, event_id, timestamp, source, payload) memenuhi syarat tipe data dan format ISO8601 sebelum diproses oleh mesin deduplikasi.

Deduplication & Transaction Logic: Mesin utama yang memeriksa keunikan event berdasarkan kombinasi topic dan event_id. Logika ini diintegrasikan langsung dalam transaksi database untuk menjamin exactly-once processing.

PostgreSQL 16 Durable Store: Menggantikan penyimpanan berbasis file (SQLite) untuk mendukung concurrency control yang lebih kuat. Menggunakan fitur ON CONFLICT DO NOTHING untuk menangani deduplikasi secara atomik dan memastikan idempotency tetap efektif meskipun kontainer di-restart.

Atomic Statistics Engine: Komponen transaksional yang mengelola metrik sistem (received, unique_processed, duplicate_dropped). Menggunakan teknik Atomic Increments (UPDATE ... SET count = count + 1) pada level database untuk mencegah fenomena lost-update saat menangani ribuan event secara simultan.

Redis Message Broker: Bertindak sebagai perantara pesan internal di dalam ekosistem Docker Compose, mengatur antrean event sebelum disimpan secara permanen ke dalam storage utama.