# AUDIT2 — Trading & Research Command Center (incrementale)

> Analisi read-only al 2026-08-30. Nessuna modifica al codice (solo questo file).
> Riferimento: `AUDIT.md` (2026-08-23). Metodo: verifica diretta su git, DB
> (migrazioni), `dashboard/src`, `worker/app`, scheduler + stato d'uso reale.
> Ground truth raccolto: **379 test worker verdi (55 file), 25 test frontend (4 file)**,
> **0 file non committati**, **migrazioni 0021–0030 tutte applicate nel DB**.
> Tono: spietatamente onesto, incluso ciò che è stato costruito e mai usato.

Legenda STATO (invariata):
✅ funzionante e verificato dal vivo · 🟡 funziona ma mai verificato dall'utente ·
🔴 rotto · 🟠 incompleto/placeholder · ⚫ morto

---

## 1. COSA È CAMBIATO dall'AUDIT.md

Dall'audit precedente sono stati fatti **6 commit sostanziali** (più il restructure).
Tutto è ora committato — il debito "18 file non committati" dell'AUDIT.md è **risolto**.

| Modulo / vista aggiunto | Dove vive | Stato REALE | Note oneste |
|---|---|---|---|
| **Restructure 5 sezioni** (Mercati/Asset/Decidi/Portafoglio/Ricerca + Guida) | `App.jsx` | ✅ | La proposta §6 dell'AUDIT.md è stata implementata (commit `555ea0d`). |
| **ASSET unificato** (Decision board + Prospettive come fold, top-band condizioni\|odds\|distribuzione) | `DecisionBoard.jsx` | 🟡 | Merge fatto (commit `08d6f09`). Mai confermato d'uso dall'utente. |
| **Combinato multi-orizzonte** (opzioni+condizionato+tilt calibrato, pesi da track record, adozione OOS) | `DecisionBoard.jsx`, `prospects/combine.py` | 🟡 | Gira, test verdi. Tilt oro 1s = +0.02 verificato da me, non dall'utente. |
| **Calibrazione indicatori + FDR** (block bootstrap, n effettivo, Benjamini-Hochberg) | `Ricerca › Calibrazione`, `calibration.py` | 🟡 | Girata: **21 sopravvissuti su 462** (erano 128 gonfiati). L'utente ha VISTO il numero gonfiato → ha chiesto il fix. Post-fix mai rivisto. |
| **Job manager** (calibrate/prospects in background, progress, watchdog) | `api.py`, `useJobStatus.js` | 🟡 | Risolve il 409 "già in corso". Verificato via API da me; l'utente non ha premuto "Ricalibra" in UI. |
| **Portafoglio reale per ISIN + import CSV + plausibilità + doppia valuta** | `Portafoglio › Reale` + landing, `PortfolioReal.jsx`, `portfolio*.py` | ✅ | **L'UNICO modulo davvero USATO e iterato dall'utente.** 42 righe importate dal suo foglio reale, bug trovati e corretti *insieme* (prezzi n/d, valuta carico, BYD −€102). Vedi §5. |
| **Controllo di plausibilità** del carico vs prezzo storico | `PlausibilityPanel` | 🟡 | Girato da me: 17 plausibili / 9 sospette / 3 non verificabili. L'utente non ha ancora premuto il pulsante in UI. |
| **Bilanci storici + traiettoria** (QoQ/YoY, inflessioni, sparkline) | `Asset › Fondamentali`, `fundamentals_trajectory.py` | 🟡 | Ingestion girata: 54 trimestri, MSFT ha 7 trimestri. Mai confermato a schermo dall'utente. |
| **Tono delle comunicazioni** (Haiku) + upload trascrizione | `Asset › Fondamentali`, `providers/tone` | 🟠 | **Nessuna lettura "valutabile" esiste**: le news sono headline → tutte "non valutabile" (onesto). Il path valutabile (trascrizione incollata) è solo testato, MAI usato con testo reale. |
| **Episodi** (drawdown / bull-year pluriennali, n<10 → niente %) | `Ricerca › Episodi`, `Episodes.jsx` | 🟡 | 4° sotto-tab di Ricerca. Mai usato. **Nota: NON esiste un modulo "movimenti estremi" separato** — i drawdown sono qui (vedi §3). |
| **Serie debito USA** (GFDEGDQ188S, deficit) come driver macro measured | `config`, calibrazione | 🟡 | Peso 0 = contesto; misurato ma n bassa (quarterly). |
| **Fix costo-valuta EUR** (carico sempre in EUR) | `lib/portfolio.js` | ✅ | Verificato: BYD da +€3.038 (sbagliato) a −€102. Parte del flusso portafoglio usato. |
| **Fix prezzi n/d** (ultima chiusura non nulla) | `App.jsx`, `prices_job.py` | ✅ | Verificato: GOOGL/AVGO/MSFT tornati a prezzare. |

**Riepilogo #1**: 1 modulo ✅ pienamente vissuto (portafoglio), il resto 🟡/🟠
"funziona ma nessuno l'ha usato". Il pattern dell'AUDIT.md **si ripete**: costruzione
> verifica reale.

---

## 2. LA STRUTTURA A 5 SEZIONI TIENE ANCORA?

**Sì nell'ossatura, no nei dettagli.** Le 5 sezioni (+ Guida) reggono e ogni flusso
mappa a una sezione. MA la frammentazione è **ricominciata dentro le sezioni**:

- **RICERCA è tornata a 4 sotto-tab**: Backtest · Calibrazione · Esperimento · **Episodi** (nuovo).
  L'AUDIT.md voleva UN laboratorio di evidenza; ora sono 4 destinazioni con etichette
  anti-data-snooping quasi identiche. **Re-frammentazione.**
- **PORTAFOGLIO ha 4 sotto-tab**: Posizioni & rischio · **Reale** · Andamento · Alert.
  "Posizioni" (trade ≤3 settimane) e "Reale" (long book per ISIN) sono **due superfici
  di portafoglio** che l'utente deve tenere a mente separate.
- **PortfolioReal è montato DUE volte**: in cima alla landing *Mercati* E in *Portafoglio › Reale*
  (l'ho messo sulla landing quando hai insistito "deve stare nella prima pagina").
  Stesso componente, due punti d'ingresso — piccola duplicazione che ho introdotto io.
- **ASSET si è invece consolidato bene**: combinato + traiettoria + tono + prospettive
  sono fold DENTRO il decision board, non tab nuovi. Qui la struttura ha tenuto.

**Verdetto #2**: l'ossatura a 5 tiene; la malattia si è spostata **dentro** Ricerca e
Portafoglio. Non siamo tornati ai 10 sotto-tab, ma abbiamo 2 sezioni che si stanno
ri-frammentando (4+4) e un componente montato 2 volte.

---

## 3. DUPLICAZIONI NUOVE (oltre a quelle mai risolte)

**Mai risolte dall'AUDIT.md** (ancora aperte):
- **Base rate (streak) vs Storico condizionato (regimi)** — l'unificazione engine era
  "in sospeso" nell'AUDIT.md ed è **ancora in sospeso**. Due implementazioni della
  stessa domanda ("frequenza storica con n"). Nessun commit l'ha toccata.
- **Livello scelto / odds impliciti** ancora in Board, Bench, Prospettive.

**Nuove:**
- **Tre viste di "pattern storici" in Ricerca**: Episodi (drawdown/bull-year pluriennali) ·
  Esperimento eventi (event-study paper) · (+ Backtest regole). Rispondono a sfumature
  diverse ma condividono la filosofia "cosa è successo storicamente, con n". "Movimenti
  estremi" che citi **non esiste come vista a sé**: è il blocco *drawdown* dentro Episodi.
- **Tre viste di valutazione su un titolo**: (a) P/E context (trailing/forward + percentile
  storia ricostruita), (b) pannello Fondamentali, (c) Traiettoria (che include ricavi/margini
  come la crescita del pannello Fondamentali). Ricavi YoY e margini appaiono sia in
  "Crescita & qualità" sia nella Traiettoria. Sovrapposizione reale.
- **Due "storici valutazione"**: il P/E percentile *ricostruito* (yfinance, in fetch) e il
  nuovo `valuation_snapshots` *accumulato* (own_history). Convivono nello stesso pannello
  con due n diversi — confonde.
- **Due superfici portafoglio**: Posizioni & rischio (trade) vs Portafoglio reale (holdings) —
  con la concentrazione tematica calcolata in entrambe su basi diverse (size×prezzo×mult vs valore EUR).

---

## 4. DEBITO E ROTTURE

**Risolto dall'AUDIT.md** (buone notizie):
- ✅ **0 file non committati** (era 18). Tutto in git.
- ✅ **Migrazioni 0021–0030 TUTTE applicate** nel DB (verificato). Nessuna in sospeso.
- ✅ **Componenti morti rimossi**: `PositionForm.jsx`, `PositionsList.jsx` non esistono più.
- ✅ **Test frontend nati**: da 0 a 4 file (bench, expectancy, experiment, portfolio), 25 test.
- ✅ **Bug proxy Prospettive** committato; **bug prezzi n/d** e **valuta carico** corretti.

**Aperto / nuovo:**
- 🟠 **9 righe portafoglio SOSPETTE** (plausibilità): Alphabet 2ª tranche **€301.77 vs €154 (+96%)**,
  IGLN.L +26%, IS3N/VWCE/ENEL +19–25% (carico ≈ prezzo attuale, non del giorno d'acquisto).
- 🔴 **Ticker sbagliato: IBTM.L** è iShares Treasury **7-10yr**, ma il tuo ISIN (IE00B3VWN393)
  è il **3-7yr**. Il prezzo mostrato è di un altro strumento.
- 🟠 **2 titoli non risolti**: **BTCW.MI** (Bitcoin, ticker inesistente su yfinance) e
  **VanEck Uranium** (ISIN `IE00M7V94E1` malformato, 11 caratteri) → Crypto €0, riga n/d.
- 🟠 **3 righe non verificabili** (VUAA.DE 2022, MEUD.PA 2023, BTCW.MI): prezzo storico assente.
- 🟠 **Tono: nessuna lettura valutabile esiste** (solo "non valutabile"). Il valore reale
  arriva solo se carichi una trascrizione — mai fatto.
- 🟠 **Valutazione own-history n=1** ("storia insufficiente"): si riempie in settimane di run.
  Il **placeholder valutazione 3-5a nelle Prospettive** (strato C dell'AUDIT.md): l'accumulo
  è partito nel BOARD, ma **non è verificato** che `prospects/valuation.py` lo legga → probabilmente
  ancora placeholder lato Prospettive.
- 🟡 **Test frontend parziali**: coprono bench/expectancy/experiment/portfolio. **NON** coprono
  `gate.js`, `concentration.js`, `risk.js`, `useJobStatus.js`, `options.js`, la matematica del BL.
  La logica più critica del rischio resta mirror non testato in JS.
- 🟠 **Expectancy/Kelly, Journal review**: ancora ~0 trade reali chiusi → "in raccolta dati".
- 🟠 **Esperimento eventi**: ancora pochi eventi + **sorpresa n/d** (FMP non popola actual/forecast).
- 🟡 **Telegram alert**: dispatch reale ancora mai verificato end-to-end.

**⚠ Feature che dipendono da job schedulati che NON girano a Mac spento/dormiente**
(tutte, launchd locale, nessun VPS — il debito infrastrutturale più grave):
1. `prices_ingestion` (ogni 15m) — prezzi/cambi stantii se il Mac dorme.
2. `fundamentals_ingestion` (**settimanale Lun 08:00**) — se il Mac dorme lunedì mattina, salta la settimana: storico bilanci + tono + `valuation_snapshots` non accumulano.
3. `ai_briefing_morning` (**06:30**) — finestra di sonno tipica → briefing del giorno perso.
4. `decision_board` (**mezzanotte**) — board non ricostruiti → traiettoria/tono/plausibilità mostrano dati vecchi all'apertura.
5. `prospects` (giornaliero), `event_experiment` (ogni 5m), `macro_ingestion` (22:30),
   `ai_tagging`/`ai_impact`, `calendar`, `news`, `figures`, `options` (23:00), `alerts` (10m).

→ **15 job**. `misfire_grace_time=None` recupera al risveglio, ma un rilascio dati o una finestra
oraria persa nel sonno **non si recupera**. La "prima schermata sempre fresca" è **impossibile
senza deploy 24/7**. Questo pesa più di ogni problema di UI.

- ⚠ **RLS Supabase ancora disabilitato** (dev). Da abilitare prima di qualsiasi esposizione.

---

## 5. COSTRUITO E MAI USATO (la metrica che conta)

**Un solo modulo ha interazione utente reale: il PORTAFOGLIO.** È l'unico che hai
importato con i tuoi dati veri, guardato, e sul quale abbiamo iterato *insieme* (prezzi
n/d, valuta del carico, BYD, plausibilità). Tutto il resto è 🟡/🟠.

**Zero interazione utente reale** (costruiti, funzionano nei test, mai "vissuti"):
- Combinato multi-orizzonte, Prospettive (post-fix), Bench (7 input), Options desk,
  Expectancy/Kelly, Backtest, **Calibrazione post-FDR**, Esperimento eventi, **Episodi**,
  **Traiettoria bilanci**, **Tono** (nessuna lettura valutabile), Alert/Telegram, Journal review AI.

Contatore brutale: **~13 viste costruite : 1 usata**. L'AUDIT.md diceva "molte viste potenti
ma mai usate"; da allora ne abbiamo aggiunte **~5** (combinato, calibrazione-FDR, episodi,
traiettoria, tono) e ne è stata *vissuta* **1 nuova** (portafoglio). Il rapporto costruito/usato
**è peggiorato**, non migliorato — tranne che il modulo vissuto è ora quello giusto.

---

## 6. PROPOSTA

### A) Consolidare / eliminare (debito, non nuove feature)
1. **Ricerca: da 4 a 1.** Un solo "Laboratorio" con selettore interno (regola / fattore /
   evento / episodio), non 4 tab. Condividono la stessa filosofia e le stesse etichette.
2. **PortfolioReal montato una volta sola.** Decidere: o è la landing (Mercati) o è il tab
   Portafoglio. Non entrambi. (Vista la tua richiesta: **landing**, e togliere il sotto-tab "reale".)
3. **Unificare "Posizioni & rischio" e "Portafoglio reale"** in una sola vista con un filtro
   *long-book vs trade*: la concentrazione tematica va calcolata una volta, su una base sola.
4. **Base rate ↔ Storico condizionato**: chiudere finalmente l'unificazione (aperta da 2 audit).
   Un solo "storico con n effettivo", con lo streak come uno dei regimi.
5. **Valutazione unica su un titolo**: fondere P/E-context + own-history + la parte crescita/margini
   della Traiettoria in UN pannello fondamentali. Oggi ricavi/margini appaiono due volte.
6. **Correggere i dati sporchi del portafoglio PRIMA di aggiungere altro**: IBTM.L (ticker
   sbagliato), BTCW.MI e VanEck (irrisolti), le 9 sospette. Un portafoglio con 9 righe ⚠ e 3 n/d
   non è una "prima schermata" affidabile.

### B) Cosa MANCA per la "prima schermata" che vuoi
*(portafoglio + watchlist con valore combinato + anomalie + top notizie/eventi/utili)*, in ordine:

1. **Portafoglio già in cima alla landing** — ✅ c'è (valore EUR, P&L, categorie). Manca: renderlo
   il blocco principale, non "sopra i mercati".
2. **Valore combinato patrimonio + mercati in un colpo d'occhio** — oggi sono due blocchi
   separati (PortfolioReal poi MarketsOverview). Serve UNA riga di sintesi in alto:
   patrimonio EUR · P&L · esposizione mega-cap tech · heat trading.
3. **Anomalie in evidenza inline** — la plausibilità è dietro un pulsante. Portarla come
   **badge sulle righe + un contatore "9 da controllare"** in cima, non un check manuale.
4. **Top notizie/eventi/utili condensati** — esistono sparsi (Catalysts, InstrumentNews,
   earnings nel board). Serve UN pannello "oggi conta questo": prossimi utili dei tuoi titoli,
   3 catalizzatori, 3 news rilevanti alle TUE posizioni.
5. **Fix dati portafoglio** (IBTM.L, BTCW.MI, VanEck, 9 sospette) — senza, la schermata mente.
6. **Deploy 24/7 (VPS)** — senza, la "prima schermata" mostra dati di ieri se il Mac ha dormito.
   Questo è il vero blocco: nessuna quantità di UI lo aggira.

---

## 7. VERDETTO (5 righe)

Il progetto è in **consolidamento nell'ossatura, accumulo nelle feature**. Buone notizie
reali: 5 sezioni tenute, tutto committato, migrazioni applicate, morti rimossi, test
frontend nati, tre bug veri corretti. Ma il rapporto **costruito : usato è ~13:1** e ne
abbiamo aggiunte altre 5 mai vissute; Ricerca e Portafoglio si ri-frammentano; base-rate/
condizionato è aperto da due audit. La svolta è che **per la prima volta UN modulo (il
portafoglio) è davvero usato e iterato** — è l'àncora attorno a cui consolidare. La priorità
non è aggiungere: è **pulire i dati del portafoglio, unificare le viste-doppione, e mettere
il worker 24/7**, altrimenti la "prima schermata" resta bella e stantia.
