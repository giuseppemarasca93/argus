# MVP 0.1

## Input

Un piccolo elenco di feed RSS, pagine web e query di ricerca approvate manualmente.

## Pipeline

1. acquisizione della pagina o del feed;
2. estrazione del testo principale;
3. calcolo dell'hash e deduplicazione;
4. salvataggio del contenuto originale e dei metadati;
5. classificazione per settore e tipo di segnale;
6. estrazione di aziende, problemi dichiarati, clienti e tecnologie;
7. generazione di un brief giornaliero con citazioni alle fonti.

## Output minimo

- nuove fonti raccolte;
- tre segnali più rilevanti;
- problemi ricorrenti;
- ipotesi generate;
- elementi da verificare manualmente.

## Criterio di successo

Dopo due settimane il sistema deve aver prodotto almeno una shortlist di cinque problemi specifici e tre categorie di potenziali clienti, ciascuna supportata da più fonti indipendenti.
