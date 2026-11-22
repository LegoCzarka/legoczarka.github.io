import argparse
import html
import json
import os
import re
import time
from datetime import datetime, timezone
import requests

BASE = "https://rebrickable.com/api/v3"
API_KEY = os.environ.get("REBRICKABLE_KEY", "").strip()
USER_TOKEN = os.environ.get("REBRICKABLE_USER_TOKEN", "").strip()
DATA_JSON_PATH = "docs/data/sets.json"
DATA_JS_PATH = "docs/data/sets.js"

WISHLIST_KEYWORDS = (
    "wish",
    "marze",
    "marzeń",
    "marzen",
    "wanted",
    "prezent",
    "chcę",
    "chce",
    "kupic",
    "kupić",
    "lista życzeń",
    "lista zyczen",
)

# Reguły kategorii: (nazwa_kategorii, wzorzec_regex) — granice słów chronią przed fałszywymi dopasowaniami (np. "cargo" != "car")
CATEGORY_RULES = [
    ("Straż pożarna", r"\b(?:fire|firefighter|firetruck)\b|straż"),
    ("Policja", r"\b(?:police|prison|prisoner|pursuit|precinct)\b|policj"),
    ("Lotnisko i samoloty", r"\b(?:airport|airplane|plane|flight|ultra\s+light|helicopter|jet)\b|samolot|lotnisk"),
    (
        "Budowa i koparki",
        r"\b(?:construction|loader|bulldozer|cement|excavator|backhoe|crane|digger)\b|kopark|budow",
    ),
    ("Farma i traktory", r"\b(?:tractor|farm|sheep|harvester|barn)\b|traktor"),
    ("Pociągi i tramwaje", r"\b(?:train|streetcar|tram|station|locomotive)\b|pociąg|tramwaj"),
    (
        "Ratownictwo",
        r"\b(?:ambulance|medical|hospital|treatment|rescue|lifeguard)\b|ratunk|karetk|szpital",
    ),
    ("Kosmos", r"\b(?:space|spaceship|spacecraft|drone|mars|rocket|astronaut|lunar)\b|kosmos"),
    (
        "Wyścigi i auta",
        r"\b(?:race|racing|sports\s+car|supercar|ferrari|f1|monster\s+jam|monster\s+truck|racer|patriot|rebel|motorcycle|motorbike|speedster|kart|car|buggy|rally)\b",
    ),
    ("Zamek i Rycerze", r"\b(?:castle|knight|knights|monarch|magic|wizard)\b|zamek|rycerz"),
    ("Piraci", r"\b(?:pirate|pirates|treasure)\b|pirac"),
    ("Zwierzęta i stwory", r"\b(?:dragon|dinosaur|dinosaurs|animal|animals)\b|smok|dinozaur"),
    ("Świąteczne", r"\b(?:advent|christmas|snowman|santa|holiday|seasonal)\b|świątecz"),
]

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "LegoCzarkaCatalog/1.1"})


def api_get(path, params=None, max_retries=3):
    if not API_KEY:
        raise SystemExit("Brak REBRICKABLE_KEY (GitHub Secret).")
    url = path if path.startswith("http") else f"{BASE}{path}"
    headers = {"Authorization": f"key {API_KEY}"}

    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            r = SESSION.get(url, headers=headers, params=params, timeout=30)
            if r.status_code == 429:
                retry_after = r.headers.get("Retry-After")
                try:
                    delay = max(1.0, min(float(retry_after), 30.0)) if retry_after else 2.5 * attempt
                except ValueError:
                    delay = 2.5 * attempt
                print(f"Limit API (429) dla {url} — czekam {delay:.1f}s (próba {attempt}/{max_retries})")
                time.sleep(delay)
                continue
            if 500 <= r.status_code < 600 and attempt < max_retries:
                delay = 2.0 * attempt
                print(f"Błąd serwera ({r.status_code}) dla {url} — ponawiam za {delay:.1f}s")
                time.sleep(delay)
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException as exc:
            last_err = exc
            if attempt < max_retries:
                delay = 2.0 * attempt
                print(f"Błąd sieci dla {url}: {exc} — ponawiam za {delay:.1f}s")
                time.sleep(delay)
            else:
                raise
    if last_err:
        raise last_err
    raise RuntimeError(f"Nie udało się pobrać danych z {url} po {max_retries} próbach.")


def api_get_all_results(path, params=None):
    """Pobiera wszystkie strony wyników z endpointu Rebrickable."""
    params = dict(params or {})
    params.setdefault("page_size", 1000)
    results = []
    next_url = path
    while next_url:
        data = api_get(next_url, params=params if next_url == path else None)
        results.extend(data.get("results", []))
        next_url = data.get("next")
        if next_url:
            time.sleep(0.5)
    return results


def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


def set_sort_key(item):
    """Klucz sortowania: najpierw rocznik, potem numer zestawu liczbowo."""
    year = int(item.get("year") or 0)
    raw = str(item.get("set_num") or "")
    clean = raw.split("-")[0]
    num_val = int(clean) if clean.isdigit() else 0
    return (year, num_val, raw)


def fetch_themes_map():
    """Pobiera słownik serii LEGO (theme_id -> {name, parent_id}) i rozwiązuje główne serie."""
    themes_raw = {}
    try:
        items = api_get_all_results("/lego/themes/")
        for t in items:
            tid = t.get("id")
            if tid is not None:
                themes_raw[tid] = {
                    "id": tid,
                    "name": t.get("name"),
                    "parent_id": t.get("parent_id"),
                }
    except Exception as e:
        print(f"Uwaga: nie udało się pobrać listy serii (/lego/themes/): {e}")

    def resolve_theme(theme_id):
        if not theme_id or theme_id not in themes_raw:
            return None, None
        sub = themes_raw[theme_id]["name"]
        cur = themes_raw[theme_id]
        visited = {theme_id}
        while cur.get("parent_id") and cur["parent_id"] in themes_raw and cur["parent_id"] not in visited:
            visited.add(cur["parent_id"])
            cur = themes_raw[cur["parent_id"]]
        root = cur.get("name")
        if root == sub:
            return root, None
        return root, sub

    return resolve_theme


def infer_theme_fallback(set_num, year, name=""):
    """Awaryjne rozpoznawanie serii po numerze zestawu i roku, gdy brakuje theme_id."""
    clean = str(set_num or "").split("-")[0]
    y = int(year) if str(year or "").isdigit() else 0
    n = (name or "").lower()

    if y and y < 2000:
        if clean.startswith("62"):
            return "Pirates", None
        if clean.startswith("60"):
            return "Castle", None
        if clean.startswith("64"):
            return "Town", "Paradisa"
        return "Town", "Classic Town"

    if clean.startswith("60"):
        return "City", None
    if clean.startswith("42"):
        return "Technic", None
    if clean.startswith("31") or clean.startswith("306"):
        return "Creator", "Creator 3-in-1" if clean.startswith("31") else "Polybag"
    if clean.startswith("71"):
        return "Ninjago", None
    if clean.startswith("77"):
        return "Sonic The Hedgehog", None
    if clean.startswith("11"):
        return "Classic", None
    if "city" in n:
        return "City", None
    if "technic" in n:
        return "Technic", None
    return None, None


def infer_category_pl(name="", theme_name="", subtheme_name=""):
    """Automatycznie przypisuje polską kategorię tematyczną dla nowych zestawów."""
    hay = f"{name or ''} {theme_name or ''} {subtheme_name or ''}".lower()
    for category, pattern in CATEGORY_RULES:
        if re.search(pattern, hay):
            return category
    return "Pojazdy miejskie"


def fetch_polish_name(set_num, en_name):
    """
    Automatycznie pobiera lub tłumaczy polską nazwę nowego zestawu LEGO:
    1. Próbuje pobrać oficjalną polską nazwę z polskiego katalogu promoklocki.pl.
    2. Jeśli zestawu tam nie ma, tłumaczy nazwę angielską przez darmowy endpoint Google Translate.
    """
    if not en_name:
        return None
    clean_num = str(set_num or "").split("-")[0].strip()

    # 1) Spróbuj pobrać oficjalną polską nazwę z polskiego katalogu promoklocki.pl
    if clean_num.isdigit():
        try:
            r = SESSION.get(
                f"https://promoklocki.pl/{clean_num}",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
            )
            if r.status_code == 200:
                m = re.search(r"<title>(.*?)</title>", r.text, re.IGNORECASE | re.DOTALL)
                if m:
                    raw_title = html.unescape(m.group(1)).strip()
                    # Format zazwyczaj: "LEGO City 60414 Remiza strażacka z wozem strażackim - porównaj ceny..."
                    raw_title = re.split(r"\s+[-–|]\s+", raw_title)[0].strip()
                    # Wytnij prefix "LEGO ... <numer> "
                    cleaned = re.sub(
                        rf"^LEGO®?\s+.*?\b{re.escape(clean_num)}\s+",
                        "",
                        raw_title,
                        flags=re.IGNORECASE,
                    ).strip()
                    if cleaned and cleaned != raw_title and len(cleaned) > 2 and cleaned.lower() != en_name.lower():
                        return cleaned
        except Exception:
            pass

    # 2) Automatyczne tłumaczenie przez darmowy endpoint Google Translate (EN -> PL)
    try:
        r = SESSION.get(
            "https://translate.googleapis.com/translate_a/single",
            params={"client": "gtx", "sl": "en", "tl": "pl", "dt": "t", "q": en_name},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data and isinstance(data[0], list):
                translated = "".join(part[0] for part in data[0] if part and part[0]).strip()
                if translated:
                    return translated[0].upper() + translated[1:]
    except Exception as e:
        print(f"Uwaga: nie udało się przetłumaczyć nazwy '{en_name}': {e}")

    return None


def is_wishlist_setlist(setlist_obj):
    """Sprawdza, czy dana lista zestawów na Rebrickable to Lista Marzeń (Wishlist)."""
    name = (setlist_obj.get("name") or "").lower().strip()
    if any(k in name for k in WISHLIST_KEYWORDS):
        return True
    if setlist_obj.get("is_buildable") is False:
        return True
    return False


def parse_set_item(item, resolve_theme, existing_cache):
    set_num = safe_get(item, "set", "set_num") or item.get("set_num") or item.get("set")
    if not set_num:
        return None

    qty = item.get("quantity")
    if qty is None:
        qty = item.get("qty")
    if qty is None:
        qty = 1

    base_obj = item.get("set") if isinstance(item.get("set"), dict) else item
    cached = existing_cache.get(set_num, {})

    name = base_obj.get("name") or cached.get("name")
    year = base_obj.get("year") or cached.get("year")
    num_parts = base_obj.get("num_parts") if base_obj.get("num_parts") is not None else cached.get("num_parts")
    set_img_url = base_obj.get("set_img_url") or cached.get("set_img_url")
    set_url = base_obj.get("set_url") or base_obj.get("url") or cached.get("set_url")
    theme_id = base_obj.get("theme_id") or cached.get("theme_id")

    # Jeśli brakuje podstawowych danych, dociągnij szczegóły setu
    if not name or not year or num_parts is None or not set_img_url or not theme_id or not set_url:
        try:
            time.sleep(1.1)
            details = api_get(f"/lego/sets/{set_num}/")
            name = name or details.get("name")
            year = year or details.get("year")
            if num_parts is None:
                num_parts = details.get("num_parts")
            set_img_url = set_img_url or details.get("set_img_url")
            theme_id = theme_id or details.get("theme_id")
            set_url = set_url or details.get("set_url") or details.get("url")
        except Exception:
            pass

    if not set_url:
        set_url = f"https://rebrickable.com/sets/{set_num}/"

    theme_name, subtheme_name = resolve_theme(theme_id)
    if not theme_name:
        theme_name = base_obj.get("theme_name") or cached.get("theme_name")
        subtheme_name = subtheme_name or cached.get("subtheme_name")
    if not theme_name:
        theme_name, subtheme_name = infer_theme_fallback(set_num, year, name)

    # Polska nazwa zestawu: z cache lub automatycznie pobrana / przetłumaczona
    # Jeśli tłumaczenie się nie powiedzie, zapisujemy None, aby kolejna synchronizacja mogła ponowić próbę.
    name_pl = cached.get("name_pl")
    if not name_pl and name:
        name_pl = fetch_polish_name(set_num, name)

    entry = {
        "set_num": set_num,
        "name": name or set_num,
        "name_pl": name_pl,
        "year": year,
        "num_parts": num_parts,
        "theme_id": theme_id,
        "theme_name": theme_name,
        "subtheme_name": subtheme_name,
        "category_pl": cached.get("category_pl") or infer_category_pl(name, theme_name, subtheme_name),
        "quantity": int(qty) if str(qty).isdigit() else qty,
        "set_img_url": set_img_url,
        "set_url": set_url,
    }
    return entry


def check_cooldown_elapsed(cooldown_hours):
    """Zwraca (ok_to_run, remaining_seconds) na podstawie generated_at z obecnego sets.json."""
    if not cooldown_hours or cooldown_hours <= 0 or not os.path.exists(DATA_JSON_PATH):
        return True, 0
    try:
        with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
            old_data = json.load(f)
        gen = old_data.get("generated_at")
        if not gen:
            return True, 0
        last_dt = datetime.fromisoformat(str(gen).replace("Z", "+00:00"))
        elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
        limit_sec = cooldown_hours * 3600.0
        if elapsed < limit_sec:
            return False, max(0, int(limit_sec - elapsed))
    except Exception as e:
        print(f"Uwaga: nie udało się sprawdzić czasu ostatniej synchronizacji: {e}")
    return True, 0


def parse_args():
    parser = argparse.ArgumentParser(description="Pobiera kolekcję LEGO z Rebrickable do docs/data/.")
    parser.add_argument(
        "--cooldown-hours",
        type=float,
        default=0,
        help="Minimalny odstęp w godzinach od ostatniej aktualizacji (0 = brak limitu).",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    ok_to_run, remaining_sec = check_cooldown_elapsed(args.cooldown_hours)
    if not ok_to_run:
        rem_h = remaining_sec // 3600
        rem_m = (remaining_sec % 3600 + 59) // 60
        print(
            f"Pominięto synchronizację: od ostatniej aktualizacji nie minęło jeszcze {args.cooldown_hours:g}h "
            f"(pozostało ok. {rem_h}g {rem_m}m)."
        )
        return

    if not USER_TOKEN:
        raise SystemExit("Brak REBRICKABLE_USER_TOKEN (GitHub Secret).")

    # Wczytaj dotychczasowy sets.json jako cache (przyspiesza działanie i chroni polskie opisy)
    existing_cache = {}
    if os.path.exists(DATA_JSON_PATH):
        try:
            with open(DATA_JSON_PATH, "r", encoding="utf-8") as f:
                old_data = json.load(f)
                for s in old_data.get("sets", []) + old_data.get("wishlist", []):
                    if s.get("set_num"):
                        existing_cache[s["set_num"]] = s
        except Exception:
            pass

    resolve_theme = fetch_themes_map()

    # Sprawdź listy zestawów użytkownika (podział na posiadane vs Lista Marzeń)
    wishlist_list_ids = set()
    try:
        setlists = api_get_all_results(f"/users/{USER_TOKEN}/setlists/")
        for sl in setlists:
            sl_id = sl.get("id")
            if sl_id is not None and is_wishlist_setlist(sl):
                wishlist_list_ids.add(sl_id)
    except Exception as e:
        print(f"Uwaga: nie udało się pobrać setlists: {e}")

    # Pobierz wszystkie zestawy użytkownika
    results = api_get_all_results(f"/users/{USER_TOKEN}/sets/")

    owned_map = {}
    wishlist_map = {}

    for item in results:
        list_id = item.get("list_id")
        parsed = parse_set_item(item, resolve_theme, existing_cache)
        if not parsed:
            continue
        snum = parsed["set_num"]
        if list_id in wishlist_list_ids:
            wishlist_map[snum] = parsed
        else:
            if snum in owned_map:
                owned_map[snum]["quantity"] = (owned_map[snum].get("quantity") or 1) + (parsed.get("quantity") or 1)
            else:
                owned_map[snum] = parsed

    # Jeśli lista marzeń nie wróciła przez /users/{token}/sets/, dociągnij ją bezpośrednio z list życzeń
    for wl_id in wishlist_list_ids:
        try:
            wl_items = api_get_all_results(f"/users/{USER_TOKEN}/setlists/{wl_id}/sets/")
            for item in wl_items:
                parsed = parse_set_item(item, resolve_theme, existing_cache)
                if parsed and parsed["set_num"] not in owned_map:
                    wishlist_map[parsed["set_num"]] = parsed
        except Exception:
            pass

    # Usuń z listy marzeń zestawy, które już są posiadane
    for snum in list(wishlist_map.keys()):
        if snum in owned_map:
            del wishlist_map[snum]

    out_owned = list(owned_map.values())
    out_wishlist = list(wishlist_map.values())

    out_owned.sort(key=set_sort_key, reverse=True)
    out_wishlist.sort(key=set_sort_key, reverse=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sets": out_owned,
        "wishlist": out_wishlist,
    }

    os.makedirs("docs/data", exist_ok=True)
    with open(DATA_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    with open(DATA_JS_PATH, "w", encoding="utf-8") as f:
        f.write("window.LEGO_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n")

    print(
        f"Zapisano {len(out_owned)} posiadanych zestawów oraz {len(out_wishlist)} z listy marzeń "
        f"do {DATA_JSON_PATH} i {DATA_JS_PATH}"
    )


if __name__ == "__main__":
    main()
