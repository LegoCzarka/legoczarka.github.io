import os, json, time
from datetime import datetime, timezone
import requests

BASE = "https://rebrickable.com/api/v3"
API_KEY = os.environ.get("REBRICKABLE_KEY", "").strip()
USER_TOKEN = os.environ.get("REBRICKABLE_USER_TOKEN", "").strip()

def api_get(path, params=None):
    if not API_KEY:
        raise SystemExit("Brak REBRICKABLE_KEY (GitHub Secret).")
    url = f"{BASE}{path}"
    headers = {"Authorization": f"key {API_KEY}"}
    r = requests.get(url, headers=headers, params=params, timeout=30)
    if r.status_code == 429:
        # throttling - poczekaj i spróbuj ponownie 1 raz
        time.sleep(2.5)
        r = requests.get(url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def safe_get(d, *keys, default=None):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

def main():
    if not USER_TOKEN:
        raise SystemExit("Brak REBRICKABLE_USER_TOKEN (GitHub Secret).")

    # 1) pobierz listę setów użytkownika
    data = api_get(f"/users/{USER_TOKEN}/sets/", params={"page_size": 1000})
    results = data.get("results", [])

    out = []
    for item in results:
        # v3 bywa zagnieżdżone - spróbuj kilku układów
        set_num = safe_get(item, "set", "set_num") or item.get("set_num") or item.get("set")
        qty = item.get("quantity") or item.get("qty") or 1

        base_obj = item.get("set") if isinstance(item.get("set"), dict) else item

        name = base_obj.get("name")
        year = base_obj.get("year")
        num_parts = base_obj.get("num_parts")
        set_img_url = base_obj.get("set_img_url")
        set_url = base_obj.get("set_url") or base_obj.get("url") or (f"https://rebrickable.com/sets/{set_num}/" if set_num else None)
        theme_name = base_obj.get("theme_name")

        # 2) Jeśli brakuje kluczowych pól, dociągnij szczegóły setu (wolniej, ale raz dziennie OK)
        if set_num and (not name or not year or not num_parts or not set_img_url):
            try:
                # UWAGA: limit ~1 request/sec - śpij dla bezpieczeństwa
                time.sleep(1.1)
                details = api_get(f"/lego/sets/{set_num}/")
                name = name or details.get("name")
                year = year or details.get("year")
                num_parts = num_parts or details.get("num_parts")
                set_img_url = set_img_url or details.get("set_img_url")
                theme_name = theme_name or details.get("theme_name")
                set_url = set_url or details.get("set_url") or details.get("url")
            except Exception:
                pass

        if not set_num:
            continue

        out.append({
            "set_num": set_num,
            "name": name or set_num,
            "year": year,
            "num_parts": num_parts,
            "theme_name": theme_name,
            "quantity": int(qty) if str(qty).isdigit() else qty,
            "set_img_url": set_img_url,
            "set_url": set_url,
        })

    out.sort(key=lambda x: (x.get("year") or 0, x.get("set_num")), reverse=True)

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
        "sets": out
    }

    os.makedirs("docs/data", exist_ok=True)
    with open("docs/data/sets.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"Zapisano {len(out)} zestawów do docs/data/sets.json")

if __name__ == "__main__":
    main()
