# Zestawy LEGO Czarka (GitHub Pages + Rebrickable)

Ta paczka tworzy darmową stronę statyczną na GitHub Pages, która **raz dziennie w nocy** aktualizuje listę Twoich zestawów z Rebrickable.

## Jak uruchomić (15–20 minut, bez serwera)

1) Załóż konto na GitHub i stwórz repozytorium, np. `zestawy-lego-czarka`
2) Wgraj tu wszystkie pliki (foldery `.github/`, `docs/`, `scripts/`)
3) W repo: **Settings → Pages**
   - Source: `Deploy from a branch`
   - Branch: `main`
   - Folder: `/docs`
4) Rebrickable:
   - wygeneruj **API Key**
   - wygeneruj **User Token** (dla API v3)
5) W repo: **Settings → Secrets and variables → Actions → New repository secret**
   - `REBRICKABLE_KEY` = Twój API Key
   - `REBRICKABLE_USER_TOKEN` = Twój user token
6) Poczekaj na pierwszy run w zakładce **Actions** (albo uruchom ręcznie: `workflow_dispatch`)

Twoja strona będzie pod:
`https://TWOJ_LOGIN.github.io/zestawy-lego-czarka/`

## Co można łatwo dodać
- filtrowanie po Theme
- licznik części łącznie
- podstrony (np. instrukcje, ulubione)
