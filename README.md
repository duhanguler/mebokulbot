# MEB Okul Bilgileri Çekme Scripti

Bu Python script'i, Türkiye Cumhuriyeti Millî Eğitim Bakanlığı'nın (MEB) web sitesinden okul bilgilerini (il, ilçe, okul adı, bilgi linki ve harita linki) çekmek için geliştirilmiştir. Selenium kütüphanesini kullanarak web sayfasında gezinir, verileri toplar ve JSON formatında kaydeder. Script, performansı artırmak ve işlemi hızlandırmak için çoklu thread (iş parçacığı) kullanır.

**GitHub Reposu:** [duhanguler/mebokulbot](https://github.com/duhanguler/mebokulbot)

## Özellikler

-   **Veri Çekme**: MEB'in okul listeleme sayfasından okul bilgilerini toplar.
-   **Otomatik Sayfalama**: Sitedeki tüm sayfaları otomatik olarak gezer.
-   **Çoklu Thread Desteği**: Veri çekme işlemini hızlandırmak için birden fazla tarayıcı örneği (headless modda) paralel olarak çalıştırır.
-   **Periyodik Kayıt**: Uzun süren işlemlerde veri kaybını önlemek için toplanan verileri belirli aralıklarla `okullar_partial.json` dosyasına kaydeder.
-   **Nihai Kayıt**: Tüm veriler toplandıktan sonra `okullar.json` dosyasına tam listeyi kaydeder.
-   **Hata Yönetimi**: Sayfa yükleme, veri ayrıştırma gibi olası hataları yakalamaya çalışır ve hatalı sayfaları tekrar denemek üzere kuyruğa ekler.
-   **Optimize Edilmiş Tarayıcı Ayarları**: Daha hızlı yükleme ve daha az kaynak tüketimi için headless tarayıcı ayarları (resimlerin, eklentilerin devre dışı bırakılması vb.) içerir.
-   **Toplam Sayfa Tahmini**: Script başlamadan önce toplam işlenecek sayfa sayısını tahmin etmeye çalışır.

## Gereksinimler

-   Python 3.6 veya üzeri
-   Google Chrome tarayıcısı
-   ChromeDriver (Python script'i ile aynı dizinde veya PATH'e eklenmiş olmalı ve kurulu Chrome versiyonu ile uyumlu olmalı)

## Kurulum

1.  **Projeyi Klonlayın (İsteğe Bağlı)**:
    ```bash
    git clone [https://github.com/duhanguler/mebokulbot.git](https://github.com/duhanguler/mebokulbot.git)
    cd mebokulbot
    ```

2.  **Python Kütüphanelerini Yükleyin**:
    Gerekli Python kütüphanelerini `pip` kullanarak yükleyebilirsiniz:
    ```bash
    pip install selenium
    ```
    (Eğer bir `requirements.txt` dosyası eklerseniz, `pip install -r requirements.txt` komutu daha pratik olur.)

3.  **ChromeDriver'ı İndirin**:
    -   Mevcut Google Chrome versiyonunuzu kontrol edin (`chrome://settings/help`).
    -   Chrome versiyonunuzla uyumlu ChromeDriver'ı [resmi ChromeDriver indirme sayfasından](https://chromedriver.chromium.org/downloads) indirin.
    -   İndirdiğiniz `chromedriver.exe` (Windows) veya `chromedriver` (Linux/macOS) dosyasını Python script'inizin bulunduğu dizine kopyalayın veya sisteminizin PATH ortam değişkenine ekleyin.

## Kullanım

    ```bash
    python app.py
    ```
Script çalışmaya başladığında, tahmini toplam sayfa sayısını gösterecek ve ardından verileri çekmeye başlayacaktır. İşlem sırasında konsolda ilerleme durumu ve olası hatalar hakkında bilgi mesajları görüntülenecektir.

**Script İçindeki Ayarlanabilir Parametreler:**

-   `BASE_URL`: Veri çekilecek web sitesinin adresi. (Varsayılan: `https://www.meb.gov.tr/baglantilar/okullar/index.php`)
-   `MAX_WORKERS`: Aynı anda çalışacak tarayıcı (işçi) sayısı. (Varsayılan: `3`)
-   `SAVE_INTERVAL`: Verilerin periyodik olarak `okullar_partial.json` dosyasına kaydedilme aralığı (saniye). (Varsayılan: `30`)

## Çıktı Dosyaları

-   `okullar_partial.json`: Script çalışırken belirli aralıklarla kaydedilen kısmi veriler. Bir hata durumunda veya işlemin yarıda kesilmesi durumunda buradan devam edilebilir veya en azından o ana kadar toplanan veriler kurtarılabilir.
-   `okullar.json`: Tüm veriler başarıyla çekildikten sonra oluşturulan nihai JSON dosyası. Her bir okul için aşağıdaki bilgileri içerir:
    ```json
    [
      {
        "il": "İL ADI",
        "ilce": "İLÇE ADI",
        "okul_adi": "OKUL ADI",
        "bilgi_link": "BİLGİ SAYFASI LİNKİ",
        "harita_link": "HARİTA LİNKİ"
      }
      // ... diğer okullar
    ]
    ```

## Önemli Notlar ve Sorumluluk Reddi

-   Bu script, MEB'in web sitesinin mevcut yapısına göre tasarlanmıştır. Web sitesinde yapılacak değişiklikler script'in çalışmasını etkileyebilir.
-   Web scraping (veri kazıma) yaparken hedef web sitesinin kullanım koşullarına ve `robots.txt` dosyasına saygı göstermek önemlidir. Sunucuya aşırı yük bindirmemek için `MAX_WORKERS` sayısını makul tutun ve sık istek göndermekten kaçının.
-   Bu script eğitim ve kişisel kullanım amaçlıdır. Elde edilen verilerin kullanımı ve paylaşımı konusunda yasal sorumluluk kullanıcıya aittir.
-   Script'in headless modda çalışması için gerekli ayarlar yapılmıştır, ancak bazı sistemlerde veya web sitesi güncellemelerinde sorunlar yaşanabilir.

## Katkıda Bulunma

Katkılarınız her zaman kabulümdür! Hata raporları, özellik istekleri veya pull request'ler için lütfen GitHub reposu üzerinden [Issues](https://github.com/duhanguler/mebokulbot/issues) veya [Pull Requests](https://github.com/duhanguler/mebokulbot/pulls) bölümlerini kullanın.

## Lisans

Bu proje GNU Lisansı altında lisanslanmıştır. Detaylar için `LICENSE` dosyasına bakınız.

## Olası Geliştirmeler

-   Daha gelişmiş hata yönetimi ve yeniden deneme mekanizmaları.
-   Kaldığı yerden devam etme özelliği (örneğin, `okullar_partial.json` dosyasını okuyarak).
-   Belirli illere veya ilçelere göre filtreleme seçeneği için komut satırı argümanları.
-   Verilerin CSV veya SQLite gibi farklı formatlarda kaydedilmesi.
-   Proxy desteği.
-   `robots.txt` otomatik kontrolü ve buna uyum.
-   Daha dinamik sayfa sayısı tespiti ve sayfalama yönetimi.
-   Kullanıcı arayüzü (örn: Streamlit veya Flask ile basit bir web arayüzü).
