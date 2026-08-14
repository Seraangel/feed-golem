# Golem RSS

Dieses Projekt speichert Artikel aus dem offiziellen Golem-Atom-Feed in SQLite und erstellt daraus einen statischen RSS-2.0-Feed.

Der GitHub-Workflow ruft `https://rss.golem.de/rss.php?feed=ATOM1.0` alle fünf Minuten ab, ergänzt die Artikeldatenbank und veröffentlicht `public/rss.xml` über GitHub Pages. Der Golem-Feed wird direkt übernommen; es findet kein Web-Scraping statt.

## Lokale Nutzung

```powershell
python -m pip install -r requirements.txt
python -m unittest discover -s tests -p "test_*.py"
python scripts/update_feed.py --db data/articles.sqlite --out public/rss.xml --limit 1000
```

## GitHub Pages

Aktiviere für dieses Repository GitHub Pages mit **GitHub Actions** als Quelle. Nach einem erfolgreichen Lauf liegt der Feed unter:

```text
https://Seraangel.github.io/feed-golem/rss.xml
```

Die erzeugte `rss.xml` enthält bis zu 1000 der neuesten gespeicherten Artikel. Sind weniger als 1000 Artikel in der SQLite-Datenbank vorhanden, enthält sie entsprechend weniger Einträge. GitHub Pages ist statisch: Query-Parameter können die Feed-Größe nicht verändern.

Der `channel`-Kopf enthält einen standardkonformen Atom-Self-Link auf die veröffentlichte RSS-Datei sowie das von Golem bereitgestellte kleine Logo über das RSS-Standardfeld `image`. Artikelbeschreibungen werden als Klartext ausgegeben, damit eingebettetes Quell-HTML die RSS-Kompatibilität nicht beeinträchtigt.

## Zeitplan

Der interne GitHub-`schedule`-Trigger wird nicht verwendet, da GitHub geplante Läufe bei hoher Last verzögern oder verwerfen kann. Ein kostenloser Cloudflare Worker in [`cloudflare-scheduler`](cloudflare-scheduler) löst den Workflow stattdessen per GitHub `repository_dispatch` aus.

Der Cloudflare Worker wird alle fünf Minuten (UTC) aufgerufen. Im Worker gilt
anschließend folgender, sommerzeitfester Zeitplan in `Europe/Berlin`:

```text
06:00–22:55  alle fünf Minuten
23:00–05:59  nur zur vollen Stunde
```

Die einmalige Einrichtung steht in [`cloudflare-scheduler/README.md`](cloudflare-scheduler/README.md). Die Python-Logik, die SQLite-Datenbank, die Git-Backups und GitHub Pages bleiben unverändert.

## Monatliche Tags

Beim ersten erfolgreichen Lauf am Monatsersten erstellt der Workflow einen
annotierten Tag im Format `YYYY.MM`, zum Beispiel `2026.08`. Der Tag verweist
auf den aktuellen Stand von `main` und wird in der Zeitzone `Europe/Berlin`
bestimmt.

## Gespeicherte Daten

Die SQLite-Datenbank `data/articles.sqlite` speichert nur Metadaten aus dem offiziellen Golem-Feed:

- `url`
- `title`
- `summary`
- `published_at`
- `first_seen_at`
- `updated_at`
