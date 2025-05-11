from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
import json
import time
import concurrent.futures # Bu script'te doğrudan kullanılmıyor ancak çoklu işlem için faydalı bir kütüphane.
import threading
import queue
import re # Regex işlemleri için eklendi

# Sabitler
BASE_URL = "https://www.meb.gov.tr/baglantilar/okullar/index.php"  # Veri çekilecek web sitesinin adresi
MAX_WORKERS = 3  # Aynı anda çalışacak tarayıcı (işçi) sayısı
SAVE_INTERVAL = 30  # Verilerin periyodik olarak kaydedilme aralığı (saniye)

def setup_driver():
    """Optimize edilmiş ayarlarla bir Chrome sürücüsü (driver) ayarlar."""
    options = Options()
    options.add_argument("--headless=new")  # Tarayıcıyı arayüz olmadan (headless modda) çalıştırır
    options.add_argument("--disable-extensions")  # Eklentileri devre dışı bırakır
    options.add_argument("--disable-dev-shm-usage")  # /dev/shm kullanımını devre dışı bırakır (Linux'ta önemli)
    options.add_argument("--no-sandbox")  # Sandbox modunu devre dışı bırakır (Linux'ta önemli)
    options.add_argument("--disable-images")  # Daha hızlı yükleme için resimleri devre dışı bırakır
    options.add_argument("--blink-settings=imagesEnabled=false") # Resimlerin yüklenmesini engeller (alternatif yöntem)
    # options.add_argument("--disable-javascript")  # Eğer çalışıyorsa JavaScript'i devre dışı bırakmayı deneyin (Bu site için JS gerekli olabilir)

    # Performans ayarları
    options.add_argument("--disable-animations") # Animasyonları devre dışı bırakır
    options.add_argument("--disable-smooth-scrolling") # Yumuşak kaydırmayı devre dışı bırakır

    # Sayfa yükleme stratejisini 'eager' olarak ayarlar (tüm kaynakların yüklenmesini beklemez)
    options.page_load_strategy = 'eager'

    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(30)  # Sayfa yükleme zaman aşımını 30 saniye olarak ayarlar
    return driver

def worker_thread(thread_id, page_queue, result_queue):
    """Sayfaları işleyen işçi (worker) thread fonksiyonu."""
    driver = setup_driver() # Her thread için yeni bir driver oluşturulur

    try:
        # Sürücüyü başlat ve sayfayı ayarla
        driver.get(BASE_URL)

        # Sayfa başına 100 öğe göstermeyi ayarla
        try:
            select_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "dt-length-0")) # Sayfa başına öğe sayısı seçme elementi
            )
            select = Select(select_element)
            select.select_by_visible_text("100") # Görünür metni "100" olan seçeneği seçer
            time.sleep(1)  # Sayfanın güncellenmesi için kısa bir bekleme
        except Exception as e:
            print(f"Thread {thread_id}: Sayfa başına öğe ayarlama hatası: {e}")

        # Kuyruktan sayfaları işle
        while not page_queue.empty(): # Kuyrukta işlenecek sayfa olduğu sürece döner
            try:
                page_num = page_queue.get(timeout=1) # Kuyruktan sayfa numarasını alır (1 saniye zaman aşımı)
            except queue.Empty: # Kuyruk boşsa döngüden çıkar
                break

            try:
                # Belirli bir sayfaya git
                if page_num > 1: # Eğer işlenecek sayfa 1. sayfa değilse
                    current_page_text = driver.find_element(By.CSS_SELECTOR, ".dt-paging-button.current").text # Mevcut aktif sayfa numarasını bulur
                    current_page = int(current_page_text) if current_page_text.isdigit() else 1 # Sayısal ise integer'a çevir, değilse 1 kabul et

                    # Eğer mevcut sayfa ile hedef sayfa arasındaki fark büyükse, sayfayı yeniden yükleyip baştan gitmek daha hızlı olabilir
                    if abs(current_page - page_num) > 5: # Eşik değeri 5 (isteğe bağlı değiştirilebilir)
                        driver.get(BASE_URL) # Sayfayı yeniden yükle
                        time.sleep(1) # Yüklenmesi için bekle

                        # Sayfa başına 100 öğe göstermeyi tekrar ayarla
                        select_element_reload = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.ID, "dt-length-0"))
                        )
                        select_reload = Select(select_element_reload)
                        select_reload.select_by_visible_text("100")
                        time.sleep(1)
                        current_page = 1 # Sayfa yeniden yüklendiği için mevcut sayfa 1 oldu

                    # Hedef sayfaya gitmek için "ileri" veya "geri" butonlarına tıkla
                    # Bu döngü, mevcut sayfadan hedef sayfaya tek tek ilerler.
                    # Hedef sayfa numarasını doğrudan girmek için bir yol varsa (örn: input alanı) daha verimli olabilir.
                    # Ancak bu sitede doğrudan sayfa numarası girme özelliği görünmüyor.
                    while current_page != page_num:
                        if page_num > current_page:
                            next_button = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, ".dt-paging-button.next:not(.disabled)")) # Tıklanabilir "ileri" butonu
                            )
                            driver.execute_script("arguments[0].click();", next_button) # JavaScript ile tıklama (bazen daha stabil çalışır)
                            current_page += 1
                        elif page_num < current_page:
                            # Eğer hedef sayfa mevcut sayfadan küçükse ve fark büyükse, en başa dönüp ilerlemek
                            # yerine doğrudan ilgili "önceki" sayfaya gitmek daha mantıklı olabilir.
                            # Ancak mevcut yapı sırayla gitmeye odaklı.
                            # Geri gitme butonu genellikle daha az kullanılır, bu yüzden "next" kadar optimize edilmemiş olabilir.
                            # En iyisi, hedef sayfaya en yakın sayfadan ilerlemek ya da gerekirse sayfayı yeniden yüklemektir.
                            # Bu örnekte, büyük geri adımlar için yeniden yükleme zaten yukarıda ele alındı.
                            # Küçük geri adımlar için:
                            prev_button = WebDriverWait(driver, 10).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, ".dt-paging-button.previous:not(.disabled)")) # Tıklanabilir "geri" butonu
                            )
                            driver.execute_script("arguments[0].click();", prev_button)
                            current_page -=1
                        else: # current_page == page_num
                            break
                        # Sayfanın güncellenmesi için dinamik bekleme.
                        # ".dt-processing" div'i kaybolana kadar bekleyebilir veya belirli bir elementin güncellenmesini bekleyebilir.
                        # Şimdilik kısa bir sabit bekleme kullanıyoruz.
                        WebDriverWait(driver, 10).until( # Sayfanın güncellendiğini teyit etmek için mevcut sayfa numarasının değişmesini bekle
                             EC.text_to_be_present_in_element((By.CSS_SELECTOR, ".dt-paging-button.current"), str(current_page))
                        )
                        # time.sleep(0.5) # Sayfanın güncellenmesi için kısa bir bekleme (dinamik bekleme ile değiştirilebilir)

                # Mevcut sayfadan verileri çıkar
                schools = [] # Bu sayfadaki okulları tutacak liste

                # Tablonun yüklenmesini bekle
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#icerik-listesi tbody tr")) # Tablo satırlarının varlığını kontrol et
                )

                # Tüm satırları al
                rows = driver.find_elements(By.CSS_SELECTOR, "#icerik-listesi tbody tr") # Tablodaki tüm satırları (tr) seçer

                for row in rows: # Her bir satır için
                    try:
                        cols = row.find_elements(By.TAG_NAME, "td") # Satırdaki tüm hücreleri (td) seçer
                        if len(cols) == 3: # Eğer hücre sayısı 3 ise (beklenen format)
                            tam_ad = cols[0].text.strip() # İlk hücre: İl - İlçe - Okul Adı
                            bilgi_link_element = cols[1].find_element(By.TAG_NAME, "a") # İkinci hücredeki link elementi
                            bilgi_link = bilgi_link_element.get_attribute("href") if bilgi_link_element else None # Linkin href değeri
                            harita_link_element = cols[2].find_element(By.TAG_NAME, "a") # Üçüncü hücredeki link elementi
                            harita_link = harita_link_element.get_attribute("href") if harita_link_element else None # Linkin href değeri

                            try:
                                # "İl - İlçe - Okul Adı" formatını ayırmaya çalış
                                parts = tam_ad.split(" - ", 2) # En fazla iki kere " - " ile ayırır
                                if len(parts) == 3:
                                    il, ilce, okul_adi = parts
                                    schools.append({
                                        "il": il.strip(),
                                        "ilce": ilce.strip(),
                                        "okul_adi": okul_adi.strip(),
                                        "bilgi_link": bilgi_link,
                                        "harita_link": harita_link
                                    })
                                else:
                                    # Eğer format beklenenden farklıysa, ham veriyi kaydet veya logla
                                    print(f"Thread {thread_id} - Sayfa {page_num}: Beklenmeyen okul adı formatı: {tam_ad}")
                                    schools.append({
                                        "tam_ad_raw": tam_ad, # Ham veriyi farklı bir anahtarla kaydet
                                        "bilgi_link": bilgi_link,
                                        "harita_link": harita_link
                                    })
                            except Exception as e:
                                print(f"Thread {thread_id} - Sayfa {page_num}: Okul verisi ayrıştırma hatası: {e} - Veri: {tam_ad}")
                        else:
                            print(f"Thread {thread_id} - Sayfa {page_num}: Beklenmeyen sütun sayısı: {len(cols)} - Satır: {row.text}")
                    except Exception as e:
                        print(f"Thread {thread_id} - Sayfa {page_num}: Satır işleme hatası: {e}")

                print(f"Thread {thread_id} - Sayfa {page_num}: {len(schools)} okul işlendi.")
                result_queue.put((page_num, schools)) # İşlenen verileri sonuç kuyruğuna ekler

            except Exception as e:
                print(f"Thread {thread_id} - Sayfa {page_num} işlenirken hata: {e}")
                page_queue.put(page_num)  # Hata durumunda sayfayı tekrar işlenmek üzere kuyruğa ekler

            finally:
                page_queue.task_done() # Kuyruktaki görevin tamamlandığını işaretler

    except Exception as e:
        print(f"Thread {thread_id} - Kritik hata: {e}")

    finally:
        driver.quit() # Thread işini bitirince tarayıcıyı kapatır

def saver_thread(result_queue, all_schools, processed_pages_set, total_pages_to_process):
    """Sonuçları periyodik olarak ve işlem bittiğinde kaydeden thread."""
    last_save_time = time.time()

    while True:
        try:
            page_num, schools_on_page = result_queue.get(timeout=5) # Sonuç kuyruğundan veri alır (5 saniye zaman aşımı)
            if page_num not in processed_pages_set: # Eğer sayfa daha önce işlenmediyse
                all_schools.extend(schools_on_page) # Gelen okulları ana listeye ekler
                processed_pages_set.add(page_num) # İşlenen sayfalar setine ekle
                print(f"Kaydedici: Sayfa {page_num} ({len(schools_on_page)} okul) eklendi. Toplam işlenen benzersiz sayfa: {len(processed_pages_set)}. Toplam okul: {len(all_schools)}")
            else:
                print(f"Kaydedici: Sayfa {page_num} zaten işlenmişti, atlanıyor.")

            result_queue.task_done() # Kuyruktaki görevin tamamlandığını işaretler

            # Periyodik olarak kaydet
            current_time = time.time()
            if current_time - last_save_time > SAVE_INTERVAL:
                with open("okullar_partial.json", "w", encoding="utf-8") as f:
                    json.dump(all_schools, f, ensure_ascii=False, indent=2)
                last_save_time = current_time
                print(f"Ara kayıt yapıldı: {len(all_schools)} okul.")

        except queue.Empty: # Kuyruk boşsa
            # İşlenecek sayfa kalmadıysa ve sonuç kuyruğu da boşsa thread'i sonlandır
            # total_pages_to_process ile karşılaştırarak tüm sayfaların işlendiğinden emin ol
            if page_queue.empty() and result_queue.empty() and len(processed_pages_set) >= total_pages_to_process:
                print("Kaydedici: Tüm sayfalar işlendi ve sonuç kuyruğu boş. Kaydedici sonlanıyor.")
                break
            elif len(processed_pages_set) >= total_pages_to_process and not page_queue.empty():
                # Bu durum, bazı sayfaların kuyruğa geri konulduğu ancak henüz işlenmediği anlamına gelebilir.
                # Veya bazı işçilerin hala çalıştığı anlamına gelebilir. Beklemeye devam et.
                print(f"Kaydedici: Tahmini tüm sayfalar ({total_pages_to_process}) işlendi ({len(processed_pages_set)} benzersiz), ancak sayfa kuyruğu veya işçiler hala aktif olabilir. Bekleniyor...")
            elif page_queue.empty() and result_queue.empty():
                # Bu durum, işçilerin işini bitirdiği ancak tüm sayfaların işlenmemiş olabileceği bir ara durum olabilir.
                # Eğer processed_pages_set < total_pages_to_process ise, bir sorun var demektir.
                print(f"Kaydedici: Sayfa ve sonuç kuyrukları boş. İşlenen benzersiz sayfalar: {len(processed_pages_set)} / {total_pages_to_process}")
            continue # Zaman aşımı durumunda döngüye devam et

    # Son kaydetme işlemi
    # Emin olmak için bir kez daha işlenmiş sayfalar üzerinden veri topla (nadiren gerekebilir ama garanti olur)
    final_schools_list = []
    # Bu kısım aslında all_schools listesinin zaten güncel olması gerektiği için gereksiz olabilir,
    # ancak çoklu thread'lerde veri tutarlılığı için bir kontrol olarak düşünülebilir.
    # Eğer all_schools her zaman doğru güncelleniyorsa, doğrudan all_schools kullanılabilir.
    # Şimdilik mevcut all_schools listesini kullanıyoruz.
    with open("okullar.json", "w", encoding="utf-8") as f:
        json.dump(all_schools, f, ensure_ascii=False, indent=2)
    print(f"Tüm veriler nihai olarak kaydedildi: {len(all_schools)} okul.")


def estimate_total_pages():
    """Toplam sayfa sayısını tahmin eder."""
    driver = setup_driver()
    try:
        driver.get(BASE_URL)

        # Sayfa başına 100 öğe göstermeyi ayarla
        select_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "dt-length-0"))
        )
        select = Select(select_element)
        select.select_by_visible_text("100")
        time.sleep(2) # Sayfanın güncellenmesi için bekle

        # Sayfalama bilgisini bulmaya çalış
        try:
            # Sayfalama butonlarına bak
            # En sondaki sayfa numarasını içeren butonu bulmaya çalışır. Genellikle 'dt-paging-button' sınıfına sahip olurlar.
            # Ve metni sadece sayı olan son buton (genellikle "next" veya "last" butonundan bir önceki).
            pagination_buttons = driver.find_elements(By.CSS_SELECTOR, ".dt-paging span a.dt-paging-button")
            # Alternatif CSS Seçici: ".dt-paging .dt-paging-button" (daha genel)
            # Veya daha spesifik: Sayfanın yapısına göre değişir. ".paginate_button" da yaygındır.
            # Bu sitede spesifik olarak: div.dt-paging > span > a.dt-paging-button (sayı içerenler)
            # Ya da doğrudan son sayfa butonunu hedef alabiliyorsak: ".paginate_button.last" gibi bir şeyin data-dt-idx değeri.

            if pagination_buttons:
                # Genellikle en sondan ikinci veya üçüncü buton son sayfa numarasını içerir
                # (Örn: 1, 2, ..., 543, Next, Last)
                # Bu sitede butonlar: Previous 1 ... 541 542 543 Next
                # Dolayısıyla sondan bir önceki buton (.next'ten önceki)
                # veya metni sayı olan en sondaki buton.
                last_page_number = 0
                for button in reversed(pagination_buttons): # Butonları sondan başa doğru kontrol et
                    button_text = button.text.strip()
                    if button_text.isdigit():
                        last_page_number = int(button_text)
                        print(f"Sayfalama butonlarından bulunan son sayfa numarası: {last_page_number}")
                        return last_page_number
                if last_page_number > 0: # Eğer bulunduysa döndür
                     return last_page_number

        except Exception as e:
            print(f"Sayfa sayısını butonlardan alırken hata: {e}")

        # Eğer butonlardan sayfa sayısı alınamazsa, bilgi metninden almaya çalış
        try:
            # Örnek metin: "Showing 1 to 100 of 54,298 entries"
            # Veya Türkçe: "54.298 kayıttan 1 ile 100 arasındakiler gösteriliyor"
            info_text_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "dt-info")) # Bu sitede "dt-info"
            )
            info_text = info_text_element.text
            print(f"Bilgi metni: {info_text}") # Debug için

            # Regex ile toplam giriş sayısını bul
            # Örnek: "Showing 1 to 100 of 54,298 entries" -> 54,298
            # Örnek Türkçe: "Toplam 54.298 kayıttan..." -> 54.298
            # Bu sitedeki format: "54.298 sonuç arasından 1 ile 100 arası gösteriliyor."
            match = re.search(r'(\d{1,3}(?:[.,]\d{3})*)\s+sonuç', info_text) # Binlik ayırıcıyı da hesaba katar
            if match:
                total_entries_str = match.group(1).replace('.', '').replace(',', '') # Binlik ayırıcılarını kaldır
                total_entries = int(total_entries_str)
                total_pages = (total_entries + 99) // 100  # Sayfa başına 100 öğe için tavan bölme
                print(f"Bilgi metninden hesaplanan toplam sayfa: {total_pages} (Toplam giriş: {total_entries})")
                return total_pages
            else:
                print(f"Bilgi metninden toplam giriş sayısı bulunamadı. Metin: '{info_text}'")

        except Exception as e:
            print(f"Giriş sayısını bilgi metninden alırken hata: {e}")

    except Exception as e:
        print(f"Toplam sayfa tahmin edilirken genel hata: {e}")

    finally:
        driver.quit()

    # Varsayılan olarak konservatif bir tahmin (eğer yukarıdakiler başarısız olursa)
    # Bu değer, sitenin mevcut durumuna göre güncellenmeli veya daha güvenilir bir yöntem bulunmalı.
    print("Otomatik sayfa sayısı tespiti başarısız. Varsayılan değer (543) kullanılıyor.")
    return 543 # Bu değeri manuel olarak güncelleyebilirsiniz veya script'i çalıştırıp gözlemleyebilirsiniz.

def main():
    start_time = time.time() # Başlangıç zamanını kaydet

    # Toplam sayfa sayısını tahmin et
    total_pages = estimate_total_pages()
    print(f"Tahmini {total_pages} sayfa işlenecek.")

    if total_pages == 0: # Eğer sayfa sayısı 0 olarak döndüyse, bu bir sorun olduğunu gösterir.
        print("HATA: Toplam sayfa sayısı 0 olarak tahmin edildi. Lütfen 'estimate_total_pages' fonksiyonunu kontrol edin.")
        return # Script'i sonlandır

    # Kuyrukları oluştur
    global page_queue, result_queue # Global değişkenler olarak tanımla (thread'ler erişebilsin diye)
    page_queue = queue.Queue()
    result_queue = queue.Queue()

    # İşlenecek tüm sayfaları kuyruğa ekle
    for page_num in range(1, total_pages + 1):
        page_queue.put(page_num)

    # Tüm okulları saklamak için liste
    all_schools = []
    processed_pages_set = set() # Benzersiz işlenmiş sayfaları takip etmek için set

    # Kaydedici (saver) thread'ini başlat
    # total_pages bilgisini saver_thread'e de gönderiyoruz ki ne zaman duracağını bilsin
    saver = threading.Thread(target=saver_thread, args=(result_queue, all_schools, processed_pages_set, total_pages))
    saver.daemon = True  # Ana thread sonlandığında bu thread'in de sonlanmasını sağlar
    saver.start()

    # İşçi (worker) thread'lerini başlat
    workers = []
    for i in range(MAX_WORKERS):
        worker = threading.Thread(target=worker_thread, args=(i + 1, page_queue, result_queue))
        worker.daemon = True # Ana thread sonlandığında bu thread'in de sonlanmasını sağlar
        worker.start()
        workers.append(worker)
        time.sleep(1) # Tarayıcıların aynı anda yüklenmesini biraz dağıtmak için küçük bir bekleme

    # Tüm sayfaların işlenmesini bekle (page_queue boşalana ve tüm task_done çağrıları yapılana kadar)
    page_queue.join()
    print("Tüm sayfalar işlenmek üzere dağıtıldı (page_queue.join() tamamlandı).")

    # Tüm sonuçların işlenmesini bekle (result_queue boşalana ve tüm task_done çağrıları yapılana kadar)
    result_queue.join()
    print("Tüm sonuçlar sonuç kuyruğundan alındı (result_queue.join() tamamlandı).")

    # Kaydedici thread'inin işini bitirmesini bekle
    # Kaydedici thread, page_queue ve result_queue boşaldığında ve tüm sayfalar işlendiğinde sonlanacak.
    # Timeout eklemek iyi bir pratik olabilir.
    print("Kaydedici thread'in sonlanması bekleniyor...")
    saver.join(timeout=SAVE_INTERVAL * 2) # Kayıt aralığının iki katı kadar bekle
    if saver.is_alive():
        print("Kaydedici thread zaman aşımına uğradı, ancak işlem devam ediyor olabilir veya takılmış olabilir.")


    end_time = time.time() # Bitiş zamanını kaydet
    print(f"Toplam {len(all_schools)} okul kaydedildi (işlenen benzersiz sayfa: {len(processed_pages_set)}).")
    print(f"Toplam süre: {end_time - start_time:.2f} saniye.")

if __name__ == "__main__":
    main()
