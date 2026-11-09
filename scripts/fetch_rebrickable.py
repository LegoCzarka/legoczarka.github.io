import os
import json
import time
from datetime import datetime, timezone
import requests

BASE = "https://rebrickable.com/api/v3"
API_KEY = os.environ.get("REBRICKABLE_KEY", "").strip()
USER_TOKEN = os.environ.get("REBRICKABLE_USER_TOKEN", "").strip()

WISHLIST_KEYWORDS = ("wish", "marze", "marzeń", "marzen", "wanted", "prezent", "chcę", "chce", "kupic", "kupić", "lista życzeń", "lista zyczen")


def api_get(path, params=None):
    if not API_KEY:
        raise SystemExit("Brak REBRICKABLE_KEY (GitHub Secret).")
    url = path if path.startswith("http") else f"{BASE}{path}"
    headers = {"Authorization": f"key {API_KEY}"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    if r.status_code == 429:
        time.sleep(2.5)
        r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


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
    if any(k in hay for k in ("fire", "straż")):
        return "Straż pożarna"
    if any(k in hay for k in ("police", "prison", "pursuit", "precinct", "policj")):
        return "Policja"
    if any(k in hay for k in ("airport", "airplane", "plane", "flight", "ultra light", "helicopter", "samolot", "lotnisk")):
        return "Lotnisko i samoloty"
    if any(k in hay for k in ("construction", "loader", "bulldozer", "cement", "excavator", "backhoe", "crane", "digger", "kopark", "budow")):
        return "Budowa i koparki"
    if any(k in hay for k in ("tractor", "farm", "sheep", "harvester", "traktor", "farm")):
        return "Farma i traktory"
    if any(k in hay for k in ("train", "streetcar", "tram", "station", "pociąg", "tramwaj")):
        return "Pociągi i tramwaje"
    if any(k in hay for k in ("ambulance", "medical", "hospital", "treatment", "rescue", "ratunk", "karetk", "szpital")):
        return "Ratownictwo"
    if any(k in hay for k in ("space", "spaceship", "drone", "mars", "rocket", "kosmos")):
        return "Kosmos"
    if any(k in hay for k in ("race", "racing", "sports car", "ferrari", "f1", "monster jam", "monster truck", "racer", "patriot", "rebel")):
        return "Wyścigi i auta"
    if any(k in hay for k in ("castle", "knight", "monarch", "magic", "wizard", "zamek", "rycerz")):
        return "Zamek i Rycerze"
    if any(k in hay for k in ("pirate", "treasure", "pirac")):
        return "Piraci"
    if any(k in hay for k in ("dragon", "dinosaur", "animal", "smok", "dinozaur")):
        return "Zwierzęta i stwory"
    if any(k in hay for k in ("advent", "christmas", "snowman", "santa", "holiday")):
        return "Świąteczne"
    return "Pojazdy miejskie"



def is_wishlist_setlist(setlist_obj):
    """Sprawdza, czy dana lista zestawów na Rebrickable to Lista Marzeń (Wishlist)."""
    name = (setlist_obj.get("name") or "").lower().strip()
    if any(k in name for k in WISHLIST_KEYWORDS):
        return True
    # Na Rebrickable listy życzeń mają zazwyczaj wyłączoną opcję "is_buildable"
    if setlist_obj.get("is_buildable") is False:
        return True
    return False


def parse_set_item(item, resolve_theme, existing_cache):
    set_num = safe_get(item, "set", "set_num") or item.get("set_num") or item.get("set")
    if not set_num:
        return None

    qty = item.get("quantity") or item.get("qty") or 1
    base_obj = item.get("set") if isinstance(item.get("set"), dict) else item
    cached = existing_cache.get(set_num, {})

    name = base_obj.get("name") or cached.get("name")
    year = base_obj.get("year") or cached.get("year")
    num_parts = base_obj.get("num_parts") if base_obj.get("num_parts") is not None else cached.get("num_parts")
    set_img_url = base_obj.get("set_img_url") or cached.get("set_img_url")
    set_url = base_obj.get("set_url") or base_obj.get("url") or cached.get("set_url") or f"https://rebrickable.com/sets/{set_num}/"
    theme_id = base_obj.get("theme_id") or cached.get("theme_id")

    # Jeśli brakuje podstawowych danych, dociągnij szczegóły setu
    if not name or not year or num_parts is None or not set_img_url or not theme_id:
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

    theme_name, subtheme_name = resolve_theme(theme_id)
    if not theme_name:
        theme_name = base_obj.get("theme_name") or cached.get("theme_name")
        subtheme_name = subtheme_name or cached.get("subtheme_name")
    if not theme_name:
        theme_name, subtheme_name = infer_theme_fallback(set_num, year, name)

    entry = {
        "set_num": set_num,
        "name": name or set_num,
        "year": year,
        "num_parts": num_parts,
        "theme_id": theme_id,
        "theme_name": theme_name,
        "subtheme_name": subtheme_name,
        "quantity": int(qty) if str(qty).isdigit() else qty,
        "set_img_url": set_img_url,
        "set_url": set_url,
    }
    # Zachowaj opcjonalne polskie pola jeśli były w cache
    for extra_key in ("name_pl", "category_pl"):
        if cached.get(extra_key):
            entry[extra_key] = cached[extra_key]
    if not entry.get("category_pl"):
        entry["category_pl"] = infer_category_pl(name, theme_name, subtheme_name)
    return entry


def main():
    if not USER_TOKEN:
        raise SystemExit("Brak REBRICKABLE_USER_TOKEN (GitHub Secret).")

    # Wczytaj dotychczasowy sets.json jako cache (przyspiesza działanie i chroni polskie opisy)
    existing_cache = {}
    if os.path.exists("docs/data/sets.json"):
        try:
            with open("docs/data/sets.json", "r", encoding="utf-8") as f:
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

    out_owned.sort(key=lambda x: (x.get("year") or 0, x.get("set_num") or ""), reverse=True)
    out_wishlist.sort(key=lambda x: (x.get("year") or 0, x.get("set_num") or ""), reverse=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "sets": out_owned,
        "wishlist": out_wishlist,
    }

    os.makedirs("docs/data", exist_ok=True)
    with open("docs/data/sets.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    with open("docs/data/sets.js", "w", encoding="utf-8") as f:
        f.write("window.LEGO_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n")

    print(f"Zapisano {len(out_owned)} posiadanych zestawów oraz {len(out_wishlist)} z listy marzeń do docs/data/sets.json i sets.js")


if __name__ == "__main__":
    main()
