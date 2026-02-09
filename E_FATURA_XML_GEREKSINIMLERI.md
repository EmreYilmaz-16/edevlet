# E-Fatura (UBL-TR) XML Oluşturmak İçin Gerekli Bilgiler

Bu doküman, ColdFusion ile oluşturulan örnek UBL-TR e‑Fatura XML’ine dayanarak **hangi verilerin gerekli olduğunu**, **hangi blokların zorunlu/opsiyonel olduğunu** ve **XML üretim sürecini** özetler. Amacımız, eksikleri tamamlayıp standartlara uygun bir e‑Fatura XML’i üretmek için net bir kontrol listesi sağlamaktır.

## 1) Standartlar ve Temel Ön Koşullar

- **UBL versiyonu**: UBL 2.x (örnekte `Invoice-2`).  
- **Türkiye özelleştirmesi (UBL-TR)**: `CustomizationID` ve profil bilgisi (`ProfileID`) zorunludur.  
- **XSD uyumluluğu**: `xsi:schemaLocation` içinde uygun UBL XSD dosyası bulunmalıdır.  
- **XSLT şablonu**: Görüntüleme için XSLT eklenir ve Base64 içerik olarak eklenir.  
- **İmza alanı**: `cac:Signature` bloğu UBL-TR’de zorunlu alanlardan biridir (e‑İmza ayrı süreçte atılır).

## 2) Zorunlu Üst Bilgiler (Header)

| Alan | Açıklama |
| --- | --- |
| `cbc:UBLVersionID` | UBL sürümü (ör. `2.1`) |
| `cbc:CustomizationID` | TR özelleştirme kimliği (ör. `TR1.2`) |
| `cbc:ProfileID` | Senaryo (TEMELFATURA, TICARIFATURA, IHRACAT vb.) |
| `cbc:ID` | Fatura numarası |
| `cbc:UUID` | Evrensel benzersiz ID |
| `cbc:IssueDate` / `cbc:IssueTime` | Fatura tarih/saat |
| `cbc:InvoiceTypeCode` | Fatura tipi (SATIS, IADE, ISTISNA, TEVKIFAT vb.) |
| `cbc:DocumentCurrencyCode` | Belge para birimi |
| `cbc:LineCountNumeric` | Satır sayısı |

**Not:** İade, ihracat, yolcu beraberi gibi profillerde `ProfileID` ve ek bloklar farklılaşır.

## 3) Taraf Bilgileri (Supplier / Customer)

### 3.1 AccountingSupplierParty (Satıcı)
Zorunlu alanlar:
- VKN/TCKN (`cbc:ID`)
- Firma ünvanı (`cac:PartyName/cbc:Name`)
- Adres (şehir, ilçe, ülke)
- Vergi dairesi (`cac:PartyTaxScheme`)
- İletişim (telefon, e‑posta)

Opsiyonel alanlar:
- Ticaret sicil no, MERSİS no
- Müşteri/iş ortağı kodu
- Yetkili kişi bilgisi

### 3.2 AccountingCustomerParty (Alıcı)
Zorunlu alanlar:
- VKN/TCKN
- Ünvan/Ad Soyad
- Adres (şehir, ilçe, ülke)
- Vergi dairesi
- İletişim (telefon, e‑posta)

Özel senaryolar:
- **İhracat / Yolcu Beraberi** profillerinde alıcı bilgisi `BuyerCustomerParty` altında verilir.
- **Kamu / KAMU profili** gibi senaryolarda ek alıcı bilgisi (`BuyerCustomerParty`) gerekebilir.

## 4) Referanslar ve Ek Belgeler

Sık kullanılan ek bloklar:
- `OrderReference` (sipariş referansı)
- `BillingReference` (iade faturası referansı)
- `DespatchDocumentReference` (irsaliye)
- `AdditionalDocumentReference` (XSLT, banka bilgileri, ek dokümanlar)

**XSLT ekleme** (örnekte yapılmış):
- `DocumentType` = `XSLT`
- `EmbeddedDocumentBinaryObject` içerisinde Base64 şablon.

## 5) Finansal ve Vergi Bilgileri

### 5.1 TaxTotal
- Toplam vergi tutarı (`cbc:TaxAmount`)
- Satır bazlı veya toplam bazlı vergi alt kırılımları (`TaxSubtotal`)
- Tevkifat / istisna gibi senaryolarda `TaxExemptionReasonCode` ve `TaxExemptionReason` zorunlu olabilir.

### 5.2 WithholdingTaxTotal
- Tevkifat faturalarında `WithholdingTaxTotal` kullanılır.

### 5.3 LegalMonetaryTotal
- `LineExtensionAmount`
- `TaxExclusiveAmount`
- `TaxInclusiveAmount`
- `AllowanceTotalAmount`
- `PayableAmount`

**Önemli:** Bu toplamların satır ve vergi toplamlarıyla tutarlı olması gerekir.

## 6) Satır (InvoiceLine) Bilgileri

Zorunlu:
- `cbc:ID` (satır sıra no)
- `cbc:InvoicedQuantity` (miktar + birim kodu)
- `cbc:LineExtensionAmount` (satır net tutar)
- `cac:Item` (ürün/hizmet adı)
- `cac:Price` (birim fiyat)

Opsiyonel:
- İskonto için `AllowanceCharge`
- GTİP, teslim/taşıma bilgileri (ihracat senaryosu)
- Barkod, üretici kodu, parti/seri no vb.

## 7) Döviz ve Kur Bilgileri

Belge para birimi TRY değilse:
- `PricingExchangeRate` bloğu
- Kaynak/ hedef para birimi
- Kur ve tarih

## 8) Banka ve Ödeme Bilgileri

Zorunlu olmamakla birlikte, ödeme bilgileri için:
- `PaymentMeans`
- `PayeeFinancialAccount`
- `AdditionalDocumentReference` ile IBAN, banka adı, swift vb.

## 9) Eksik Olabilecek Kritik Veriler (Kontrol Listesi)

Aşağıdaki veriler yoksa XML üretimi tamamlanamaz ya da doğrulama hatası alınır:

- UBL sürümü + TR özelleştirme bilgisi
- Fatura numarası (ID) ve UUID
- Fatura tarihi/saat
- Satıcı VKN/TCKN, ünvan, adres
- Alıcı VKN/TCKN, ünvan/ad, adres
- Satır bilgileri (miktar, birim, fiyat)
- Vergi toplamları ve parasal toplamlar
- Senaryoya uygun `ProfileID` ve `InvoiceTypeCode`

## 10) Önerilen Üretim Akışı

1. **Temel fatura verisini topla:** Şirket, müşteri, satır, vergi, kur, ödeme.
2. **Senaryoyu belirle:** TEMELFATURA / TICARIFATURA / IHRACAT / TEVKIFAT vb.
3. **UBL header’ı doldur:** `UBLVersionID`, `CustomizationID`, `ProfileID`, `ID`, `UUID`, `IssueDate`.
4. **Taraf bilgilerini ekle:** Supplier ve Customer blokları.
5. **Vergi ve toplamları hesapla:** Satır bazlı ve toplam.
6. **Satırları yaz:** `InvoiceLine` blokları.
7. **XSLT ve ek dokümanları ekle:** `AdditionalDocumentReference`.
8. **XML’i doğrula:** XSD doğrulaması, e‑Fatura testleri.
9. **İmza süreci:** XML imzalanır ve gönderilir (ENTEGRASYON).

## 11) Bizde XML Oluşturma İçin Devam Adımı

E‑fatura XML’ini üretmek için aşağıdaki bilgiler netleşmeli:

- Kullanılacak senaryo ve profil (örn. TICARIFATURA, IHRACAT)
- UBL versiyonu ve `CustomizationID`
- Fatura numarası, UUID ve tarih/saat formatı
- Satıcı ve alıcı şirket bilgileri
- Satır listesi (ürün, miktar, birim, fiyat, vergi)
- Para birimi ve kur (varsa)
- İndirim/iskonto ve ek belge ihtiyaçları

Bu bilgiler hazır olduğunda, **örnek bir UBL-TR XML şablonu** çıkarıp sisteminizde otomatik üretime geçebiliriz.
