# AUDIT — Trading & Research Command Center

> Analisi read-only al 2026-08-23. Nessuna modifica al codice.
> Metodo: verifica diretta su `worker/`, `dashboard/`, `config/`, `db/migrations/`
> + stato runtime (338 test worker verdi; migrazioni 0007–0020 tutte applicate nel DB;
> 18 file non committati). Tono: spietatamente onesto, incluso ciò che non è mai stato
> verificato dal vivo dall'utente.

Legenda STATO:
- ✅ **funzionante e verificato** (l'utente o io l'abbiamo visto produrre numeri sensati dal vivo)
- 🟡 **funziona ma mai verificato dall'utente** (gira, test verdi, ma nessuna conferma d'uso reale)
- 🔴 **rotto / valori implausibili**
- 🟠 **incompleto / placeholder dichiarato**
- ⚫ **morto** (codice presente ma non raggiungibile dalla UI)

---

## 1. INVENTARIO FUNZIONALITÀ

### Navigazione: 3 tab primari (Mercati · Trading · Guida). "Trading" contiene **10 sotto-tab**.

### A) Viste dashboard

| Vista (tab) | Cosa fa | Dati | File | Stato |
|---|---|---|---|---|
| **Mercati** (home) | Status strip (P&L, heat, violazioni, catalizzatore, briefing) + panoramica strumenti sortabile + watchlist + dettaglio strumento + briefing AI + key-figures + catalizzatori | prezzi, decision_boards, positions, events, briefings, figure_statements | `App.jsx`, `StatusStrip`, `MarketsOverview`, `Watchlist`, `InstrumentDetail`(+`PriceChart`,`InstrumentNews`), `BriefingPanel`, `KeyFigures`, `Catalysts` | ✅ |
| **Trading › Posizioni & Rischio** | Sizing calculator + gate pre-trade "Nuovo trade" + concentrazione tematica + posizioni reali (entry/prezzo/side/P&L) + posizioni test (paper) | positions, risk_settings, instruments, events, decision_boards | `SizingCalculator`, `TradeGate`, `ConcentrationWarning`, `PositionsTable`, `PaperMonitor`, `GateShared` | ✅ |
| **Trading › Decision board** | Per strumento: lancetta di confluenza (condizioni macro+tecnica), base rate, prob. implicite, segnali desk (skew/COT/event), fondamentali (titoli), freschezza macro, "cosa ha mosso", rischio-evento, ciclicità, quadro completo, doppia lente, sintesi Ae | decision_boards (JSONB), calibrations | `DecisionBoard.jsx` | ✅ (enorme, vedi §2) |
| **Trading › Decisione** (bench) | Aritmetica di UNA scommessa: odds impliciti sui tuoi livelli, rischio-evento, win-rate di pareggio (costi incl.) vs odds, confronto struttura diretta vs opzione, scala scenari €, gate + "monitora come test", confronta strumenti | decision_boards, positions, risk_settings | `DecisionBench.jsx`, `lib/bench.js` | 🟡 |
| **Trading › Prospettive** | Distribuzione esiti a 1s/1m/3m/6m/1a (+5a) da opzioni (Breeden-Litzenberger), storico condizionato (n effettivo), valutazione; fan chart; livello scelto; calibrazione | prospects (JSONB), prospect_calibrations | `Prospects.jsx`, `lib/bl`→worker | 🟡 (bug proxy corretto, **non committato**) |
| **Trading › Expectancy** | Statistiche di lungo periodo dai TUOI trade chiusi: win rate + IC, expectancy R/€, profit factor, rischio di rovina (Monte Carlo), Kelly frazionario, scorecard disciplina | positions (chiuse), risk_settings | `Expectancy.jsx`, `lib/expectancy.js` | 🟡 (serve n≥20; oggi ~0 trade reali chiusi) |
| **Trading › Ricerca** (backtest) | Backtest di regole tecniche (OOS, costi, Sharpe deflazionato, bootstrap) **+** calibrazione indicatori (IC per fattore×orizzonte) | backtest_runs, calibrations, prezzi | `Backtest.jsx`, `Calibration.jsx` | 🟡 |
| **Trading › Esperimento eventi** | Apre posizioni paper automatiche a t+5m/30m/2h/1d dopo i dati USA, misura cosa succede; risultati aggregati + calibrazione | positions (experiment=true), events | `ExperimentResults.jsx`, `lib/experiment.js` | 🟡 (1 evento finora; sorpresa n/d, vedi §3) |
| **Trading › Journal** | CRUD trade + review AI dei pattern | journal_entries | `Journal.jsx` | 🟡 |
| **Trading › Options** | Catene, IV/Greeks ricalcolati, strutture (payoff/breakeven/POP), hedge proposals | options_chains, hedge_proposals | `OptionsDesk.jsx`, `PayoffChart` | 🟡 |
| **Trading › Alert** | Regole prezzo/IV + log alert (Telegram) | alert_rules, alerts | `Alerts.jsx` | 🟡 (Telegram mai verificato end-to-end) |
| **Guida** | Teoria + glossario (tooltip single-source) | `data/guide.js`, `guide_content.md` | `Guide.jsx` | ✅ |

**Componenti ⚫ MORTI** (0 import nel codice): `PositionForm.jsx`, `PositionsList.jsx`. Codice presente, non raggiungibile — residui di iterazioni precedenti (sostituiti da `TradeGate`/`PositionsTable`).

### B) Moduli worker (per area)

| Area | Moduli | Cosa | Stato |
|---|---|---|---|
| Ingestion | `prices_job`, `macro_job`, `calendar_job`, `news_job`, `tagging_job`, `impact_job`, `figures_job`, `options_job`, `earnings`, `seed` | feed dati → storage, con retry/backoff | ✅ (news GDELT a volte 429; FMP non porta actual/forecast, vedi §3) |
| AI (server-side) | `ai/briefing`, `ai/tagging`, `ai/impact`, `ai/decision`, `ai/journal`, `ai/client` | briefing, tag, impact, sintesi decision board, review journal | ✅ briefing/decision verificati; tagging/impact 🟡 |
| Decision board | `decision/board`, `synthesis`, `implied`, `fx_signals`, `attribution`, `seasonality`, `full_picture`, `stock_news`, `bench` | assemblaggio board + tutti gli strati | ✅ core; 🟠 seasonality/valuation (vedi §3) |
| Rischio/disciplina | `risk`, `risk_report`, `gate`, `discipline`, `concentration`, `expectancy` | sizing, gate, kill-switch, expectancy, concentrazione | ✅ math testata |
| Prospects | `prospects/bl`, `conditional`, `valuation`, `calibration_metrics`, `runner`, `calibrate` | distribuzioni multi-orizzonte + calibrazione | 🟡 (bl corretto, non committato) |
| Ricerca | `backtest/*`, `calibration`, `calibration_runner` | backtest + IC indicatori | 🟡 |
| Esperimento | `experiment/surprise`, `plan`, `job`, `aggregate` | esperimento eventi paper | 🟡 |
| Alert/Notify | `alerts/engine`, `alerts/rules`, `notify/telegram`, `notify/null`, `notify/base` | edge-trigger + cooldown, dispatch Telegram | 🟡 (email = stub OFF; Telegram non verificato) |
| Providers | prices, macro(FRED), calendar(FMP+seeded), options(yfinance), positioning(CFTC), fundamentals(yfinance), news(GDELT+RSS), figures | interfacce swap-able | ✅ pattern rispettato |
| Infra | `api` (FastAPI), `scheduler` (APScheduler), `main` (CLI, 20 comandi), `storage` (base+supabase), `config` | orchestrazione | ✅ locale (launchd); ⚠ nessun deploy VPS |

---

## 2. DUPLICAZIONI E SOVRAPPOSIZIONI

**Il problema più grave del progetto.** Sono cresciute per accrezione: ogni turno ha aggiunto una vista senza consolidare.

### a) "Decision board" vs "Decisione" vs "Prospettive" — 3 viste, stesso asset
- **Decision board**: condizioni ATTUALI (lancetta, driver, tecnica, fondamentali, news) — *"com'è messo l'asset ORA"*.
- **Decisione** (bench): aritmetica di UNA scommessa specifica (entry/stop/target → win-rate di pareggio vs odds).
- **Prospettive**: distribuzione degli esiti FUTURI per orizzonte (opzioni/storico).
- **Sovrapposizione**: tutte e tre mostrano le **probabilità implicite** e il **livello scelto** (prob. sopra/sotto). Il "livello scelto" esiste in **3 posti**. Gli odds impliciti in 3 posti. La prob. su un livello è ricalcolata da 3 UI diverse.
- **Unico di ciascuna**: Board = contesto/narrativa/lancetta; Bench = payoff/costi/confronto struttura; Prospettive = distribuzione multi-orizzonte + calibrazione.

### b) Base rate (Decision board) vs Storico condizionato (Prospettive)
Entrambi = "frequenza storica dei rendimenti futuri con n". Il base rate condiziona sullo **streak**; il condizionato sui **regimi dei driver**. Stessa domanda ("cosa è successo storicamente"), due implementazioni, due etichette d'onestà diverse. Confondono.

### c) Expectancy vs Journal review
Entrambi misurano i TUOI trade chiusi. Journal review = pattern AI qualitativi; Expectancy = statistiche (win rate, R, Kelly). Si rispondono a vicenda alla domanda "come sto andando".

### d) Ricerca/Backtest vs Calibrazione indicatori vs Esperimento eventi
Tre "laboratori di evidenza":
- Backtest = una regola tecnica ha edge OOS?
- Calibrazione indicatori = ogni fattore ha IC predittivo?
- Esperimento eventi = cosa fa il prezzo dopo i dati USA?
Domanda comune: *"questo segnale/fattore/evento ha valore reale?"*. Tre viste separate, tre etichette anti-data-snooping quasi identiche. Backtest e Calibrazione condividono già il tab "Ricerca"; l'Esperimento è staccato senza motivo.

### e) Confluenza (Decision board) vs Quadro completo (titoli) vs Confronta strumenti (bench) vs Panoramica (Mercati)
Quattro modi di mettere "fattori affiancati" o "strumenti a confronto". Panoramica e Confronta-strumenti rispondono entrambi a "quale strumento guardare".

---

## 3. COSA È ROTTO O SOSPETTO

1. 🔴→🟢 **Bug proxy/unità in Prospettive (CORRETTO ma NON COMMITTATO).** Le mediane da opzioni erano −91% (oro) perché la densità BL era in unità proxy (GLD ~400) rapportata allo spot strumento (GC=F ~4437). Corretto: rendimenti relativi al proxy + fit quadratico dello smile + filtro liquidità + sanity check. Verificato: mediana 1s ≈ 0, P(sopra) 40–60%. **Rischio: la correzione vive solo nel working tree non committato.**
2. 🟠 **Point value ×1 su 10/15 strumenti.** Solo 5 hanno `contract_multiplier` (rame, DAX, nat-gas…). Per gli altri (titoli, indici via CFD) il rischio €, il P&L e gli scenari sono corretti solo se 1 unità = 1× prezzo. Per future/CFD reali il rischio è **sottostimato**. La UI lo segnala (chip "×1") ma è un'assunzione forte.
3. 🟠 **Sorpresa eventi = n/d.** L'esperimento eventi calcola la "sorpresa" da `actual`/`forecast` degli eventi, ma il calendario in DB li ha **vuoti** (arrivano dal provider *seeded*, solo date; FMP non li popola). → la tabella "per direzione della sorpresa" non si differenzia mai.
4. 🟠 **Esperimento eventi: 1 solo evento finora.** Serve n≥20 per cella → mesi/anni. Oggi è un raccoglitore vuoto, per costruzione onesto ma inutile a breve.
5. 🟠 **Valutazione (Prospettive strato C) = placeholder dichiarato.** Lo storico valutazioni non è conservato → il modulo restituisce "non disponibile". Codice presente, mai produttivo.
6. 🟠 **Seasonality/ciclicità**: gira, ma quasi sempre "nessun pattern significativo" (atteso). Utile come anti-illusione, non come segnale.
7. 🟡 **Expectancy/Kelly**: richiede n≥20 trade reali chiusi; oggi ~0 → mostra "in raccolta dati". Mai verificato con dati veri.
8. 🟡 **Telegram alert**: interfaccia pronta, engine testato, ma **dispatch reale mai verificato** end-to-end. Email = stub OFF.
9. 🟡 **DAX/rame in Prospettive**: catene opzioni USA assenti/sottili → griglia legittimamente vuota (ora con avviso). Non è un bug ma sorprende.
10. ⚫ **`PositionForm`, `PositionsList`**: componenti morti.
11. ⚠ **Scheduler & Mac in sleep**: i job (briefing 06:30, esperimento) vengono saltati se il Mac dorme (mitigato con `misfire_grace_time=None`, ma un rilascio dati in finestra di sonno si perde comunque).
12. ⚠ **RLS Supabase disabilitato** (migrazione 0003, ambiente dev). Va abilitato prima di qualunque esposizione online.

---

## 4. COMPLESSITÀ D'USO (input prima di un risultato utile)

| Vista | Input richiesti | Conoscenza implicita non spiegata |
|---|---|---|
| Mercati | 0 (si apre e legge) | — (buona) |
| Decision board | 1 (scegli strumento) [+ livello opz.] | cos'è "lancetta ≠ probabilità", divergenza |
| **Decisione** (bench) | **7** (strumento, direzione, orizzonte, entry, stop, target, rischio%) | win-rate di pareggio, moneyness, "l'edge è la tua tesi" |
| **Prospettive** | 1–2 (strumento [+ livello]) ma **ricalcolo = minuti** | risk-neutral vs mondo reale, n effettivo, coverage |
| Expectancy | 0–3 (filtri) ma **serve storico trade** | Kelly, rischio di rovina, bound inferiore |
| Ricerca/Backtest | 3+ (regola, strumento, parametri) | OOS, Sharpe deflazionato, deflazione |
| Options | 2+ (sottostante, scadenza, struttura) | Greeks, POP, moneyness |
| Journal | molti (form completo) | — |
| Alert | molti (tipo, soglia, cooldown) | edge-trigger |

**Osservazione**: le viste a più alto attrito (bench: 7 input; prospettive: attesa minuti) sono anche quelle mai verificate dall'utente. Le viste a 0 input (Mercati) sono le uniche "vissute".

---

## 5. FLUSSI REALI

1. **"Capire un asset ORA"** → Mercati (panoramica) → Decision board. *(Prospettive potrebbe servire qui ma è staccata.)*
2. **"Valutare/dimensionare UNA scommessa"** → Decisione (bench) → Options (struttura) → Posizioni&Rischio (registra/paper). *(3 tab per un flusso solo.)*
3. **"Misurare i miei risultati"** → Posizioni&Rischio → Journal → Expectancy. *(3 tab.)*
4. **"Fare ricerca / validare un'idea"** → Ricerca (backtest+calibrazione) → Esperimento eventi. *(2 tab.)*
5. **"Essere avvisato"** → Alert.

**Viste che non appartengono a nessun flusso pulito**: **Prospettive** (dovrebbe stare nel flusso 1, ma è isolata e lenta); **Esperimento eventi** (flusso 4 ma staccato e semi-vuoto). **Calibrazione indicatori** vive dentro Ricerca ma serve al Decision board (ricalibra la lancetta) — flusso incrociato non evidente.

---

## 6. PROPOSTA DI RIORGANIZZAZIONE (obiettivo 4–5 sezioni)

Oggi: 3 primari ma **10 sotto-tab in Trading**. La malattia è la frammentazione del Trading.

### Struttura proposta: **5 sezioni**

**1. MERCATI** *(invariata)* — panoramica, watchlist, dettaglio, briefing, calendario, key-figures. È il flusso 0-attrito che già funziona.

**2. ASSET** *(accorpa Decision board + Prospettive)*
Una sola vista per strumento con due livelli: in alto **le condizioni ORA** (lancetta, driver, news, fondamentali); sotto, espandibile, **le prospettive future** (distribuzione multi-orizzonte + calibrazione). Il "livello scelto" e gli odds impliciti diventano **UNO** componente condiviso.
*Perché*: rispondono alla stessa domanda ("com'è e dove può andare questo asset") e già duplicano prob. implicite e livello.
*Cosa si perde*: nulla di sostanziale; si elimina la terza copia del "livello scelto".

**3. DECIDI** *(accorpa Decisione/bench + Options + Sizing)*
Il flusso "valuta e dimensiona una scommessa": bench come vista principale, con la struttura a opzioni e il sizing come pannelli, non tab separati. Gate integrato (già c'è).
*Perché*: è un unico flusso spezzato in 3 tab. Sizing calculator è un sottoinsieme del gate.
*Cosa si perde*: Options come esplorazione libera delle catene — mantenibile come pannello "avanzato".

**4. PORTAFOGLIO** *(accorpa Posizioni & Rischio + Journal + Expectancy)*
"Cosa ho, come è andata, cosa dicono i miei numeri": posizioni reali+paper, heat/concentrazione, journal, expectancy/rischio-rovina/Kelly.
*Perché*: tutti guardano i TUOI trade. Journal review ed Expectancy sono due risposte alla stessa domanda.
*Cosa si perde*: nulla; si unifica la review.

**5. RICERCA** *(accorpa Backtest + Calibrazione indicatori + Esperimento eventi)* — **sezione "avanzata", nascosta di default**
Il laboratorio di evidenza. Le 3 viste condividono la filosofia anti-data-snooping.
*Perché*: sono per l'utente-ricercatore, non per l'operatività quotidiana.
*Cosa si perde*: nulla; si raggruppa.

**+ GUIDA** sempre accessibile. **ALERT**: spostare come pannello dentro Portafoglio o Mercati (non merita un tab).

### Da ELIMINARE del tutto
- ⚫ `PositionForm.jsx`, `PositionsList.jsx` (morti). *Si perde*: nulla.
- **Base rate** (Decision board): fonderlo nello **storico condizionato** di Prospettive/Asset (un solo "storico con n"). *Si perde*: il condizionamento sullo streak — recuperabile come uno dei regimi.
- **Panoramica** (Mercati) e **Confronta strumenti** (bench): tenerne UNO. *Si perde*: una delle due tabelle multi-strumento (identiche nello scopo).

### Risultato
Da **3 primari + 10 sotto-tab (13 destinazioni)** → **5 sezioni + Guida**. Ogni flusso di §5 mappa a UNA sezione.

---

## 7. DEBITO TECNICO

- **NON COMMITTATO (18 file)**: tutto il modulo `prospects/` (bl, conditional, valuation, calibration_metrics, runner, calibrate) + i suoi 3 file di test + migrazione **0020** + fix UI (PositionsTable entry/prezzo, ExperimentResults lista aperti/conclusioni) + wiring api/main/config/storage. **Include la correzione del bug proxy.** Rischio reale di perdita/regressione finché non committato.
- **Migrazioni**: 0007–0020 tutte applicate nel DB (verificato). `0013` non è mai esistito (salto documentato). Nessuna migrazione in sospeso.
- **Test**: 338 worker verdi, 48 file. **Zero test frontend** (nessun test su React/`lib/*.js`; verificati solo a mano con esbuild). La matematica JS (gate, bench, expectancy, experiment) è mirror non testata automaticamente.
- **Mai verificato dal vivo dall'utente**: bench, prospettive (post-fix), expectancy, calibrazione, esperimento, options desk, alert Telegram, journal review AI.
- **Infra**: gira solo in locale (launchd, Mac acceso e loggato). Nessun deploy VPS → niente 24/7 reale. Scheduler perde job durante lo sleep.
- **Sicurezza**: RLS disabilitato (dev). Da abilitare con policy prima di qualsiasi esposizione.
- **Feature del brief non costruite**: nat-gas fundamentals sub-module (EIA/NOAA/AGSI+), Directa API position sync, deploy VPS, polish mobile.
- **Dipendenze dati fragili**: yfinance (non ufficiale, rate-limit), GDELT (429 frequenti), FMP che non popola actual/forecast → sorpresa eventi n/d.

---

## SINTESI IN UNA RIGA
Il motore (worker) è solido e ben testato; il **prodotto (dashboard) è sovra-frammentato**: 10 sotto-tab con forti duplicazioni, molte viste potenti ma mai usate perché ad alto attrito o isolate dal loro flusso. La priorità non è aggiungere: è **consolidare a 5 sezioni**, committare il lavoro in sospeso (col fix del bug proxy), e portare almeno un flusso completo alla verifica reale.
