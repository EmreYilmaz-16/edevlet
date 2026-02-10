# Troubleshooting

## `Warn: Can't find .pfb for face 'Courier'`

Bu uyarı modül kodundan değil, sistemde PostScript font paketlerinin eksik
olmasından kaynaklanır (çoğunlukla `ghostscript`/`gsfonts`).

Öneri:

- Sunucuya font paketlerini kurun (`gsfonts` veya dağıtıma denk paketi).
- Odoo servis kullanıcısının font path'lerine erişebildiğini doğrulayın.

## `ERROR: couldn't write the config file`

Bu hata, PDF/report kütüphanelerinin çalışma anında konfigürasyon dosyası
oluşturmak istediği dizinin yazılabilir olmamasından kaynaklanır.

Bu modülde başlangıçta `RL_HOME` değişkeni yazılabilir bir temp dizinine
ayarlanır. Ek olarak aşağıdakileri doğrulayın:

- Container/host üzerinde `/var/tmp` veya `/tmp` yazılabilir olmalı.
- Odoo servis kullanıcısının ilgili dizinlere yazma izni olmalı.

## `psycopg2.InterfaceError: connection already closed` (cron thread)

Bu kayıt çoğunlukla PostgreSQL bağlantısının servis restart/shutdown sırasında
kapanmasıyla görülür. Kalıcı şekilde tekrar ediyorsa:

- PostgreSQL loglarını kontrol edin (restart, timeout, network reset).
- Odoo `db_maxconn`, reverse proxy timeout ve worker timeout ayarlarını gözden
  geçirin.
- Container orkestrasyonunda healthcheck/restart politikasını doğrulayın.
