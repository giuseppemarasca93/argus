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

Milestone 0.2 operativo: raccolta RSS configurabile, archivio SQLite deduplicato, estrazione deterministica di evidenze e report Markdown.

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
python -m argus extract
python -m argus evidence-report
python -m argus report
```

Il client HTTP usa lo User-Agent `Argus/0.1` e un timeout di 15 secondi. Il timeout può essere modificato, per esempio con `python -m argus collect --timeout 30`.

La raccolta salva gli articoli in `data/argus.db`; il report crea `reports/YYYY-MM-DD.md` con gli articoli acquisiti in quel giorno. L'URL canonico dell'articolo è univoco: fragment e parametri di tracking comuni vengono rimossi, mentre gli altri parametri sono conservati e ordinati. Raccolte successive non producono duplicati.

`extract` analizza titolo e summary con le regole configurabili in `extraction_rules.yaml`. Produce evidenze di tipo topic, company, technology, problem e market signal, sempre collegate all'articolo originale. L'estrazione è interamente rule-based e non usa AI generativa: i risultati sono segnali da verificare, non verità assolute.

La confidence è deterministica: `0.9` per una frase canonica esatta, `0.8` per un sinonimo configurato e `0.7` per una keyword canonica singola. `value` conserva il testo incontrato, mentre `normalized_value` contiene il valore canonico definito nelle regole.

Il comando è idempotente e, normalmente, ignora gli articoli già processati. Sono disponibili:

```bash
python -m argus extract --limit 50
python -m argus extract --rules extraction_rules.yaml --force
python -m argus evidence-report --output reports/evidence.md
```

`--force` ricalcola esclusivamente le evidenze prodotte dall'extractor deterministico `rules-v1`; eventuali evidenze di altri extractor restano intatte. L'evidence report mostra conteggi, valori più frequenti e fino a cinque articoli collegati per valore.

Argus calcola un fingerprint SHA-256 dalla rappresentazione canonica delle regole normalizzate, non dai byte del file YAML. Se la semantica delle regole cambia, gli articoli vengono rielaborati automaticamente e le precedenti evidenze di `rules-v1` vengono sostituite; modifiche di formattazione o ordine delle chiavi non causano rielaborazioni. `--force` ricalcola comunque tutte le evidenze di `rules-v1` selezionate, senza toccare quelle di altri extractor.

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
