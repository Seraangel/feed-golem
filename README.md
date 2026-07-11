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

## Zeitplan

Der Workflow verwendet folgenden Cron-Ausdruck:

```text
*/5 * * * *
```

Geplante GitHub-Actions-Läufe erfolgen in UTC und können bei hoher Auslastung verzögert werden.

## Gespeicherte Daten

Die SQLite-Datenbank `data/articles.sqlite` speichert nur Metadaten aus dem offiziellen Golem-Feed:

- `url`
- `title`
- `summary`
- `published_at`
- `first_seen_at`
- `updated_at`
