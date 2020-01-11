# keyword-scanner
Findet Keywörter in einem Text mithilfe der deutschsprachigen Wikipedia. Das Skript prüft, ob Wörter eines Textes einem Wikipedia-Eintrag zuordenbar sind. Bei Synonymen (wie zum Beispiel "Bach", das in einem Text potenziell nicht nur für das Fließgewässer, sondern auch für den Komponisten "Johann Sebastian Bach", einen Asterioden oder diverse Ortschaften stehen kann) wird mittels eines statistischen Abgleichs markanter Wörter des analysierten Textes und dem Text des Wikipedia-Artikels der wahrscheinlichste Artikel ausgewählt.

Mit keyword-scanner sich relevante Schlüsselbegriffe zur weiteren Datenanalyse eines Textes finden.

### Installation
Erforderlich sind die Python-Bibliotheken Levenshtein und spaCy (inklusive eines deutschen Sprachmoduls

```
pip install python-Levenshtein
pio install spaCy
python -m spacy download de_core_news_sm
```

### So funktioniert's

```
from get_keywords import get_keywords
text = "Auf Einladung von Wladimir Putin reist Angela Merkel zusammen mit Außenminister Heiko Maas erstmals nach langer Zeit wieder nach Moskau."
keywords = get_keywords(text)
for keyword in keywords:
     print(keyword['title'])
```
Ergebnis:
```
Einladung
Wladimir Wladimirowitsch Putin
Angela Merkel
Außenminister
Heiko Maas
Moskau
```

Hinweis: Das Programm wurde für eine MySQL geschrieben. Diese Version nutzt SQLite. Für eine performante Nutzung ist vermutlich weitere Optimierung notwendig.
