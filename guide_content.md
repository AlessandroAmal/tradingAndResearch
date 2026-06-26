# Guida d'uso — Trading & Research Command Center

> Contenuto sorgente della pagina "Guida" in dashboard. Da integrare nel modulo
> `src/data/guide.js` (così i tooltip dei campi e la pagina restano in sync) e reso
> nella vista Guide. Testi in italiano, plain language. Le definizioni sono pensate per
> essere lette anche da chi non mastica le opzioni.

---

## 0. Come usare questo cockpit (e cosa NON è)

**Cos'è.** Un centro di comando che mette in un posto solo i dati di mercato, il calendario
eventi, le news sintetizzate, gli impatti dei personaggi-chiave, il rischio delle tue posizioni
e il desk opzioni. Il suo valore è **organizzazione e disciplina**: niente ti sfugge, P&L e
rischio sono visibili a colpo d'occhio, le news diventano un briefing corto.

**Cosa NON è.** Non è una macchina che prevede il mercato. Le notizie pubbliche sono già nei
prezzi in millisecondi: questo strumento non ti dà un vantaggio predittivo, ti dà ordine e
metodo. Non è consulenza finanziaria. **Le decisioni le prendi tu** — il cockpit ti mette
davanti il contesto e mette alla prova le tue idee contro le tue regole.

**Un flusso di lavoro tipo.**
1. Mattino: leggi il **briefing** ("cosa conta adesso") e i **prossimi catalizzatori**.
2. Guarda la **watchlist** e gli impatti nel **key-figures**.
3. Prima di un trade: usa la **calcolatrice di sizing** e controlla **rischio e limiti**.
4. Apri la posizione (dal tuo broker) e **registrala** nel cockpit + nel **journal** con la tua tesi.
5. Per coperture o strutture, usa l'**options desk** (probabilità implicite, payoff, hedge).
6. Periodicamente: genera la **review del journal** per vedere i tuoi pattern.

---

## 1. Watchlist e dettaglio strumento

- **Δ giornaliera / %** — variazione del prezzo rispetto alla chiusura precedente, in valuta e
  in percentuale. È il "quanto si è mosso oggi".
- **Distanza dalle MA (20 / 50 / 200)** — di quanto il prezzo è sopra o sotto le medie mobili a
  20, 50 e 200 periodi. Contesto tecnico veloce: sopra le medie = tendenza più costruttiva,
  sotto = più debole. Non è un segnale operativo, è inquadramento.
- **ATR (14)** — *Average True Range* a 14 periodi: l'ampiezza media di oscillazione. Indica
  quanto "respira" lo strumento, utile per dimensionare lo stop in modo realistico (uno stop
  più stretto dell'ATR viene colpito dal rumore).
- **VIX** — indice della paura: misura la volatilità attesa sull'S&P 500. Sale quando il mercato
  ha paura. **Si guarda, non si tratta** (i futures/ETP sul VIX hanno decadimento). Serve a
  capire il "clima" e a scegliere i momenti per le coperture.

---

## 2. Calendario & catalizzatori

- **Tipi di evento** — riunioni delle banche centrali (**FOMC** = Fed, **ECB** = BCE), dati USA
  (**CPI** = inflazione al consumo, **PCE** = inflazione preferita dalla Fed, **NFP** = occupati
  non agricoli), dati Cina (**PMI** = indici di attività), **earnings** (trimestrali) degli
  strumenti seguiti, **EIA** (scorte gas, giovedì).
- **Impatto** — livello atteso di importanza (alto/medio/basso). Gli eventi ad alto impatto
  possono muovere parecchio i mercati: è quando serve più cautela su size e stop.
- **Countdown** — tempo che manca al prossimo evento ad alto impatto. Aiuta a non farti
  sorprendere "dentro" un trade da un dato che non avevi in mente.

---

## 3. News & briefing AI

- **Temi** — ogni notizia è etichettata per tema: Fed, UE, Cina, dazi/Trump, NVDA, Google, Musk.
  Serve a filtrare il rumore e vedere cosa tocca i tuoi strumenti.
- **Briefing del mattino / intraday** — una sintesi corta e scannabile ("cosa conta adesso")
  generata dall'AI dai news recenti + eventi imminenti + movimenti di prezzo notevoli.
- **Nota di incertezza** — ogni briefing porta sempre un caveat esplicito. È voluto: la sintesi
  **organizza e riassume, non prevede**. Leggi il briefing come una rassegna ordinata, non come
  una previsione di cosa farà il mercato.

---

## 4. Key figures (personaggi-chiave)

- **Chi** — Trump, Powell (Fed), Musk, Jensen Huang, Sundar Pichai, politica cinese.
- **Strumenti impattati** — per ogni dichiarazione, l'AI indica quali strumenti del tuo universo
  *potrebbero* essere mossi.
- **Perché conta** — una riga di spiegazione. È formulato come **"possibile influenza"**, mai
  come certezza: è una mappa di attenzione, non un segnale d'ingresso.

---

## 5. Posizioni & rischio (il cuore del cockpit)

### Parametri di una posizione
- **Strumento** — cosa stai tradando, scelto dal tuo universo.
- **Side (Long / Short)** — *Long* = al rialzo (guadagni se sale); *Short* = al ribasso/scoperto
  (guadagni se scende).
- **Size** — dimensione della posizione (unità/contratti/azioni o nozionale): quanto sei esposto.
- **Entry** — prezzo d'ingresso.
- **Stop** — *stop-loss*: il prezzo di uscita in perdita per limitare il rischio. È la cosa più
  importante: definisce quanto puoi perdere. Rischio ≈ |entry − stop| × size × moltiplicatore.
- **Target** — prezzo obiettivo di uscita in profitto.
- **Deadline** — scadenza/orizzonte della posizione (≤ 3 settimane per lo swing, oppure la
  scadenza dell'opzione). Il sistema fa il countdown e ti avvisa quando si avvicina.
- **Broker** — dove l'hai aperta. È solo registrazione: il cockpit è agnostico rispetto al broker.
- **Tesi** — perché hai aperto il trade. Serve al journal per verificare, dopo, se si è avverata.

### Concetti di rischio
- **Rischio per trade** — quanto perdi se lo stop viene colpito, in valuta e come **% del conto**.
  Il tuo limite (es. 1–2% del conto) è in impostazioni.
- **R-multiple (R:R)** — rapporto rischio/rendimento: |target − entry| ÷ |entry − stop|. Un R:R
  di 3 significa che punti a guadagnare 3 volte quanto rischi.
- **Portfolio heat** — la somma di tutti i rischi aperti contemporaneamente. È il rischio totale
  che hai "acceso" sul conto: il limite di heat evita che tante piccole posizioni sommate ti
  espongano troppo.
- **Position sizing** — il calcolo inverso: dato entry, stop e il tuo rischio% massimo, il
  sistema ti dice **quanto comprare**. È così che il rischio guida la size, non l'istinto.
- **Posizioni concorrenti** — quante posizioni aperte insieme; c'è un limite configurabile.
- **Breach (violazioni)** — bandierine quando il prezzo buca lo stop, quando heat o rischio/trade
  o numero posizioni superano i limiti, o quando una deadline si avvicina. Sono **flag**, non
  ordini: ti segnalano, decidi tu.
- **Moltiplicatore di contratto (point value)** — quanto vale un punto di prezzo per quello
  strumento. **Importante:** di default è 1, corretto per azioni e crypto; per **future/CFD**
  (oro, gas, rame, argento, indici) il valore reale è diverso da 1 — finché non lo imposti in
  configurazione, rischio e P&L su quegli strumenti sono **sottostimati**. Imposta i point value
  veri prima di fidarti dei numeri sul comparto future.

### Calcolatrice di sizing
Inserisci entry, stop e rischio% (e lo strumento, per il moltiplicatore) → ottieni la size, il
rischio aperto e l'R:R. Usala **prima** di aprire, per entrare già con la size giusta.

---

## 6. Trade journal

- **Campi** — strumento, tesi, entry/exit, size, stop, esito, e soprattutto **se la tesi si è
  avverata** (sì/no/n.a.), più note. Puoi collegare una posizione e pre-compilare i campi.
- **Esito (outcome)** — win / loss / breakeven, con P&L.
- **Review AI on demand** — la generi quando vuoi (da worker). Le **statistiche le calcola il
  codice** (win rate, R-multiple realizzato, tasso di tesi avverate, P&L); l'AI **interpreta** i
  pattern (quali setup/temi funzionano, errori ricorrenti).
- **Come leggerla** — è onesta sulla dimensione del campione: con poche voci i pattern sono
  **ipotesi tentative, non conclusioni**. Il valore vero arriva dopo decine di trade, non subito.
  Serve a vedere te stesso con dati alla mano, non a darti un verdetto.

---

## 7. Options desk (la parte più tecnica)

Il desk è di **sola analisi**: propone e calcola coperture e strutture, non invia ordini. Tutti
i numeri (volatilità implicita, Greche, probabilità) sono **ricalcolati dal codice** con il
modello di Black-Scholes — non si usa la volatilità di Yahoo, che è inaffidabile.

### Cosa sono le opzioni
- **Opzione** — un contratto che dà il diritto (non l'obbligo) di comprare o vendere un
  sottostante a un prezzo prefissato entro una scadenza.
- **Call** — diritto di **comprare** a un prezzo dato. Sale di valore se il sottostante sale.
- **Put** — diritto di **vendere** a un prezzo dato. Sale di valore se il sottostante scende.
- **Strike** — il prezzo prefissato del contratto.
- **Scadenza (expiry)** — la data entro cui l'opzione vale.
- **Premio** — il prezzo dell'opzione (quanto paghi/incassi per il contratto).
- **Bid / Ask / Mid** — prezzo in denaro / in lettera / loro punto medio. Il *mid* è la
  riferimento da cui ricaviamo la volatilità implicita.
- **ITM / ATM / OTM** — *in the money* (già con valore intrinseco), *at the money* (strike vicino
  al prezzo attuale), *out of the money* (ancora senza valore intrinseco).
- **Open Interest / Volume** — contratti aperti in essere / scambiati nella sessione. Indicano
  **liquidità**: alti = prezzi affidabili; bassi = spread larghi e numeri rumorosi.

### Volatilità implicita (IV)
La volatilità che il mercato "sconta" nel prezzo dell'opzione: l'aspettativa di quanto il
sottostante potrà muoversi (in ampiezza, **non in direzione**) fino alla scadenza. La ricaviamo
risolvendo Black-Scholes dal prezzo mid. IV alta = opzioni care, mercato che si aspetta movimenti
grandi (spesso prima di earnings o eventi).

### Le Greche (sensibilità del prezzo dell'opzione)
- **Delta (Δ)** — quanto si muove l'opzione per ogni €1 di movimento del sottostante. Indica
  anche l'esposizione equivalente in sottostante (≈ quante "azioni" rappresenta).
- **Gamma (Γ)** — quanto velocemente cambia il delta. Alto vicino all'ATM e a ridosso della
  scadenza: il rischio si muove in fretta.
- **Theta (Θ)** — il **decadimento temporale**: quanto valore perde l'opzione ogni giorno che
  passa, a parità di tutto. Per chi compra opzioni è una perdita (negativo).
- **Vega** — quanto si muove il prezzo dell'opzione per ogni punto di variazione dell'IV. Misura
  la tua esposizione alla volatilità.
- **Rho (ρ)** — sensibilità ai tassi d'interesse. Marginale per scadenze brevi.

### Probabilità di profitto (POP)
La probabilità che la struttura finisca **oltre il breakeven** a scadenza, calcolata dalla
distribuzione **implicita nei prezzi** (risk-neutral). **Punto fondamentale e onesto:** è la
probabilità che il *mercato* sconta in quell'opzione — gli "odds" impliciti nei prezzi — **non
una previsione** di cosa accadrà. È la "probabilità vera" nel senso che è reale e implicita nei
prezzi, non inventata; ma va letta come la quota di una scommessa, non come un oracolo.

### Lettura di una struttura
- **Payoff** — il profitto/perdita a scadenza al variare del prezzo del sottostante (il grafico).
- **Breakeven** — il prezzo del sottostante a cui la struttura non guadagna né perde.
- **Max loss / Max gain** — perdita e guadagno massimi della struttura.
- **Rischio/rendimento (R:R)** — rapporto tra guadagno potenziale e perdita massima.

### Le strutture
- **Leg singola** — una sola call o put. Direzionale, semplice.
- **Spread verticale** — compri e vendi due opzioni dello stesso tipo a strike diversi: rischio e
  guadagno **definiti** (entrambi limitati). Direzionale con rischio sotto controllo.
- **Put protettiva (Insurance)** — compri una put a copertura di una posizione che possiedi al
  rialzo: mette un **pavimento** alle perdite, al costo del premio. È un'assicurazione.
- **Collar (Insurance)** — put protettiva finanziata vendendo una call: protezione a costo
  ridotto (a volte quasi zero), in cambio di un **tetto** ai guadagni.

### Modalità del desk
- **Insurance** — scegli una tua holding → il desk propone put/collar con **costo, pavimento,
  breakeven e % di posizione coperta**, più il grafico. Serve a proteggere, non a speculare.
- **Directional** — costruisci una leg singola o uno spread verticale → **max loss, R:R,
  breakeven, POP** e payoff. Serve a valutare un'idea direzionale con i rischi davanti.

### Avvertenze importanti (come fidarti dei numeri)
- **Liquidità** — i numeri sono affidabili su contratti **liquidi, vicini all'ATM e a scadenza
  ravvicinata**. Su strike sottili (spread larghi, basso open interest) l'IV ricavata dal mid
  diventa rumorosa, e con lei Greche e POP.
- **Proxy ETF** — yfinance dà opzioni solo su **azioni/ETF USA**. Le esposizioni macro passano da
  ETF proxy (Nasdaq→QQQ, oro→GLD, argento→SLV, rame→CPER, gas→UNG): la copertura sulle commodity
  è quindi un'**approssimazione direzionale**, non un hedge esatto. Su single-stock (NVDA, GOOGL,
  MSFT…) la copertura è invece diretta e pulita.
- **Niente opzioni su FX e crypto** — non esistono catene su yfinance: quei sottostanti compaiono
  come "no options". È atteso.
- **Dividendi** — Black-Scholes (versione europea) non li modella: piccola imprecisione su titoli
  che pagano dividendi.
- **Dati ritardati (~15 min)** — adeguati per swing e coperture; non per scalping sull'ultimo tick.

---

## 9. Decision board (per strumento — oro)

Una vista che raccoglie in un colpo d'occhio le condizioni che pesi **prima** di un trade. **NON è
un segnale e NON è una previsione**: è il quadro che valuti tu. Il colore indica solo lo *stato*
(favorevole / contrario / attenzione), mai un'azione.

### Sintesi (lettura di confluenza)
In cima alla vista, una **lettura direzionale** (lean) con la sua forza su scala −100..+100 (es.
"moderatamente ribassista") e, espandibile, il **dettaglio per fattore**: ogni fattore col suo stato
(rialzista / ribassista / neutro), tipo (direzionale o contesto) e peso configurabile.
- La lettura è l'**allineamento delle condizioni ATTUALI**, **non** una probabilità e **non** una
  previsione del prossimo movimento. Per questo **non** vedrai mai un "X% sale/scende" calcolato da noi.
- I fattori di **contesto** (volatilità/ATR, streak, rischio evento) **non** spingono il lean; il
  rischio-evento è un *flag di cautela*, non una direzione. Se un dato manca, il fattore è **escluso**
  (non indovinato) e te lo diciamo.
- **Confronto condizioni ↔ mercato:** la lettura è affiancata alla **probabilità implicita** nelle
  opzioni (l'unico numero di probabilità, gli odds del mercato). Se le condizioni puntano da una parte
  ma il mercato è ~neutro, spesso il movimento è **già prezzato** — è l'output di sintesi più utile.
- Caveat fissi: fotografia delle condizioni attuali, non una previsione; i fattori sono deboli e
  dipendono dal regime; la probabilità del futuro è solo quella implicita.

### Confluenza
Tutte le condizioni con il loro stato: tasso reale ↑/↓, dollaro ↑/↓, streak, posizione vs MA, RSI,
ATR, prossimo evento. "Favorevole/contrario" riflette il **contesto storico** per quello strumento
(es. tasso reale in salita = vento contrario per l'oro), non una raccomandazione.

### Misure tecniche
- **Streak** — giorni consecutivi nella stessa direzione. Uno streak lungo è spesso segno di un
  **trend forte**, non di un rimbalzo garantito.
- **MA200** — media a 200 giorni: tendenza di fondo (sopra/sotto). Contesto, non segnale.
- **RSI** — sbilanciamento del movimento recente (0–100). Soglie **tarate sullo strumento** (per
  l'oro più larghe di 70/30). "Ipercomprato/ipervenduto" = attenzione, non inversione.
- **ATR** — ampiezza media di oscillazione (volatilità realizzata): per stop realistici.

### Base rate storico (onestà sul campione)
Dato lo streak attuale (es. "5 giorni giù"), conta **quante volte (n)** è già successo nel periodo e
cosa è accaduto dopo: **% di volte in salita** e rendimento medio al giorno dopo / a N giorni.
- `n` è **sempre** mostrato.
- Se `n` è sotto la soglia: *"campione insufficiente — nessuna conclusione"*.
- Se quello streak **non si è mai visto**: *"mai accaduto: nessuna base statistica"*, **non** una
  probabilità. La rarità **non** implica l'inversione (fallacia dello scommettitore).

### Probabilità implicite dalle opzioni
Dai prezzi delle opzioni (proxy GLD), il **movimento atteso ±%** e la **probabilità implicita**
(risk-neutral) che il prezzo finisca sopra/sotto il livello corrente a ~1 giorno / ~3 giorni / ~1
mese. Sono gli **odds del mercato** impliciti nei prezzi, **non una previsione**.

### Sintesi AI (opzionale)
Quando attiva, mette in parole il setup e ne segnala tensioni e incertezza. Per regola **non fa mai
una chiamata direzionale** (sale/scende, compra/vendi): descrive le condizioni, non predice.

---

## 10. Come leggere tutto con onestà

Il filo conduttore del cockpit: **niente segnali finti.**
- Le **probabilità** (POP) sono quelle implicite nei prezzi — gli odds del mercato, non profezie.
- Le **sintesi AI** (briefing, key-figures, review) organizzano e segnalano sempre l'incertezza;
  non dicono cosa succederà.
- La parte solida e affidabile è la **disciplina**: sizing corretto, limiti di rischio, R:R,
  countdown delle scadenze, e i tuoi pattern dal journal.
- "Cosa apro / come mi comporto" non è un oracolo: è il tuo contesto messo in ordine e la tua
  idea messa alla prova contro le tue regole. **La decisione resta tua.**

---

## Glossario rapido (A–Z)

- **ATR** — ampiezza media di oscillazione (volatilità realizzata).
- **ATM / ITM / OTM** — strike at/in/out of the money.
- **Base rate** — frequenza storica di cosa è successo dopo una certa situazione (es. uno streak),
  sempre con la sua numerosità `n`. Non una previsione.
- **Breakeven** — prezzo del sottostante a cui una struttura non guadagna né perde.
- **Call / Put** — diritto di comprare / vendere a strike entro scadenza.
- **Collar** — put protettiva finanziata da una call venduta (protezione con tetto ai guadagni).
- **CPI / PCE / NFP / PMI** — inflazione consumi / inflazione cara alla Fed / occupati USA / attività.
- **Delta / Gamma / Theta / Vega / Rho** — sensibilità del prezzo dell'opzione (sottostante,
  velocità del delta, tempo, volatilità, tassi).
- **FOMC / ECB / EIA** — riunione Fed / BCE / report scorte gas USA.
- **IV (volatilità implicita)** — movimento atteso dal mercato, in ampiezza non direzione.
- **Long / Short** — posizione al rialzo / al ribasso.
- **MA (20/50/200)** — medie mobili; la distanza dà il contesto di tendenza.
- **Moltiplicatore / point value** — valore di un punto di prezzo (1 per azioni/crypto, diverso
  per future/CFD — da impostare).
- **Open Interest / Volume** — liquidità di un'opzione.
- **Payoff** — profitto/perdita a scadenza al variare del sottostante.
- **POP (probabilità di profitto)** — probabilità implicita nei prezzi oltre il breakeven (odds
  del mercato, non previsione).
- **Probabilità implicita** — probabilità ricavata dai prezzi delle opzioni (risk-neutral): gli
  odds del mercato, non una profezia.
- **Portfolio heat** — somma dei rischi aperti.
- **RSI** — Relative Strength Index (0–100): sbilanciamento del movimento recente. Soglie tarate
  per strumento.
- **Tasso reale / Breakeven inflazione (FRED)** — driver macro dell'oro: rendimento decennale al
  netto dell'inflazione attesa (DFII10) e inflazione attesa a 10 anni (T10YIE).
- **Protective put** — put a copertura di un long posseduto (pavimento alle perdite).
- **R-multiple (R:R)** — rapporto rischio/rendimento.
- **Rischio per trade** — perdita se lo stop è colpito, in % del conto.
- **Spread verticale** — due opzioni stesso tipo, strike diversi: rischio e guadagno definiti.
- **Stop (stop-loss)** — prezzo di uscita in perdita; definisce il rischio.
- **Strike** — prezzo prefissato dell'opzione.
- **VIX** — indice della paura (volatilità attesa S&P 500); si guarda, non si tratta.
