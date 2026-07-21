# Argus

Argus è il nostro motore privato di intelligence per ridurre la probabilità di costruire il prodotto sbagliato.

## Obiettivo iniziale

Esplorare il climate tech, raccogliere evidenze verificabili, collegare aziende, problemi, tecnologie e segnali di mercato, quindi produrre ipotesi da validare.

## Principio guida

Argus non è il prodotto da vendere. È lo strumento interno con cui trovare un problema reale, costoso e risolvibile tramite software.

## Primo traguardo

Entro la prima iterazione Argus deve:

1. raccogliere fonti da un insieme ristretto e controllato;
2. salvare contenuto, fonte, data e metadati;
3. evitare duplicati;
4. estrarre aziende, problemi e categorie;
5. produrre un brief leggibile con fatti, ipotesi e domande aperte.

## Stato

MVP 0.1 operativo: raccolta RSS configurabile, archivio SQLite deduplicato e report giornaliero Markdown.

## Requisiti

- Python 3.12

## Installazione

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
```

Non sono richieste variabili d'ambiente. Le fonti sono configurate in `sources.yaml` con `name` e `url`.

## Utilizzo

Eseguire dalla root del repository:

```bash
python -m argus collect
python -m argus report
```

La raccolta salva gli articoli in `data/argus.db`; il report crea `reports/YYYY-MM-DD.md` con gli articoli acquisiti in quel giorno. L'URL canonico dell'articolo è univoco, quindi raccolte successive non producono duplicati.

Percorsi e data possono essere personalizzati:

```bash
python -m argus --database data/altro.db collect --sources sources.yaml
python -m argus --database data/altro.db report --date 2026-01-04 --output reports
```

Un errore relativo a un singolo feed viene registrato e non interrompe le altre fonti.

## Test

```bash
pytest
```
