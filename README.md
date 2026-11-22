# 🧱 Zestawy LEGO Czarka (GitHub Pages + Rebrickable)

Strona katalogowa kolekcji LEGO Czarka i Mateusza dostępna pod adresem:
👉 **https://legoczarka.github.io/**

Stworzona z myślą o rodzinie i znajomych szukających prezentu dla Czarka — pozwala w kilka sekund sprawdzić po numerze z pudełka lub polskiej nazwie, czy dany zestaw znajduje się już w domowej kolekcji.

---

## ✨ Główne funkcje strony

1. **🔍 Szybki Sprawdzacz Prezentu (Mamy czy nie mamy?)**
   - Po wpisaniu numeru z pudełka (np. `60414`) strona od razu wyświetla **czerwone ostrzeżenie z miniaturką pudełka** (jeśli zestaw już jest w kolekcji) albo **zielone potwierdzenie** (jeśli zestawu jeszcze nie mamy — wraz z linkiem do podglądu na LEGO.com).
   - Zawsze sprawdza pełną kolekcję (niezależnie od włączonych filtrów), obsługuje wpisywanie bez polskich znaków (np. *straz*, *smieciarka*, *pociag*) oraz kilka słów naraz.
2. **🇵🇱 Wyszukiwanie i opisy po polsku**
   - Obsługuje wyszukiwanie po polskich hasłach (np. *straż pożarna*, *policja*, *koparka*, *traktor*, *śmieciarka*, *samolot*, *pociąg*, *smok*, *dinozaury*), nawet gdy Rebrickable zwraca nazwy angielskie.
3. **🧱 Filtrowanie po seriach LEGO, tematach i udostępnianie linków**
   - Szybkie przełączanie pomiędzy kolekcją **Czarka (2000+)** a klasycznymi zestawami **Taty – Mateusza (lata 1987–1993)**, filtrowanie po seriach i dynamicznych kategoriach oraz kopiowanie bezpośrednich linków (np. `?q=60414` lub `?owner=WISHLIST`).
4. **📖 Instrukcje budowania LEGO i powiększanie pudełek**
   - Każda karta pozwala powiększyć zdjęcie pudełka na pełnym ekranie oraz jednym kliknięciem otworzyć oficjalną instrukcję PDF na stronie LEGO.com.
5. **🎯 Automatyczna Lista Marzeń (ukryta, dopóki jest pusta)**
   - Sekcja i zakładka **„🎁 Lista Marzeń”** pojawia się na stronie automatycznie tylko wtedy, gdy wrzucisz do niej chociaż jeden zestaw.
6. **🔄 Nocna synchronizacja + szybki skrót w stopce**
   - Kolekcja aktualizuje się automatycznie codziennie w nocy (`01:30 UTC`), a na dole strony znajduje się dyskretny przycisk kierujący prosto do **GitHub Actions**, aby w razie potrzeby uruchomić ręczne odświeżenie z Rebrickable.

---

## 🎁 Jak dodać zestawy do „Listy Marzeń” na Rebrickable?

Lista Marzeń jest domyślnie ukryta. Aby pojawiła się na stronie:
1. Zaloguj się na swoje konto **Rebrickable.com**.
2. Wejdź w **My LEGO → My Set Lists** i utwórz nową listę zestawów, np. o nazwie **`Lista marzeń`** (lub **`Wishlist`** / **`Prezent`**) i **odznacz** w jej ustawieniach opcję *„Include sets in this list for Build calculations”*.
3. Dodaj do tej listy wymarzone zestawy LEGO.
4. Przy kolejnej nocnej aktualizacji (lub po kliknięciu **🔄 Odśwież z Rebrickable (GitHub Actions)** w stopce strony → **Run workflow**) na stronie automatycznie pojawi się sekcja **🎯 Lista Marzeń Czarka**! Gdy usuniesz z niej wszystkie zestawy, sekcja znów sama się ukryje.
