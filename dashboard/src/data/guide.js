// Single source for the Guide page AND the inline "i" tooltips, so the two
// never drift. Content from guide_content.md (sections 0–8 + glossary).
// Static, Italian, documentation only — no financial assumptions.
//
// Keyed help dicts (FIELD_HELP / RISK_HELP / OPTION_HELP) are reused BOTH by
// the form tooltips and by the corresponding Guide definition lists.

const byKey = (arr) => Object.fromEntries(arr.map((x) => [x.key, x]))

// --- Position fields (form tooltips + §5) -----------------------------
export const FIELD_HELP = [
  { key: 'symbol', label: 'Instrument', text: 'Cosa stai tradando, scelto dal tuo universo.' },
  { key: 'side', label: 'Side', text: 'Long = al rialzo (guadagni se sale); Short = al ribasso/scoperto (guadagni se scende).' },
  { key: 'size', label: 'Size', text: 'Dimensione della posizione (unità/contratti/azioni o nozionale): quanto sei esposto.' },
  { key: 'entry', label: 'Entry', text: 'Prezzo d’ingresso.' },
  { key: 'stop', label: 'Stop', text: 'Stop-loss: il prezzo di uscita in perdita per limitare il rischio. Definisce quanto puoi perdere. Rischio ≈ |entry − stop| × size × moltiplicatore.' },
  { key: 'target', label: 'Target', text: 'Prezzo obiettivo di uscita in profitto.' },
  { key: 'deadline', label: 'Deadline', text: 'Scadenza/orizzonte della posizione (≤ 3 settimane per lo swing, o l’expiry dell’opzione). Il sistema fa il countdown e avvisa all’avvicinarsi.' },
  { key: 'broker', label: 'Broker', text: 'Dove l’hai aperta. Solo registrazione: il cockpit è agnostico rispetto al broker.' },
  { key: 'thesis', label: 'Thesis', text: 'Perché hai aperto il trade. Serve al journal per verificare, dopo, se si è avverata.' },
]
export const FIELD_HELP_BY_KEY = byKey(FIELD_HELP)

// --- Risk concepts (sizing tooltips + §5) -----------------------------
export const RISK_HELP = [
  { key: 'risk_per_trade', label: 'Rischio per trade', text: 'Quanto perdi se lo stop viene colpito, in valuta e come % del conto. Il tuo limite (es. 1–2%) è in impostazioni.' },
  { key: 'r_multiple', label: 'R-multiple (R:R)', text: 'Rapporto rischio/rendimento: |target − entry| ÷ |entry − stop|. Un R:R di 3 = punti a guadagnare 3 volte quanto rischi.' },
  { key: 'portfolio_heat', label: 'Portfolio heat', text: 'La somma di tutti i rischi aperti contemporaneamente: il rischio totale acceso sul conto. Il limite di heat evita che tante posizioni sommate ti espongano troppo.' },
  { key: 'position_sizing', label: 'Position sizing', text: 'Il calcolo inverso: dato entry, stop e il rischio% massimo, il sistema ti dice quanto comprare. Così il rischio guida la size, non l’istinto.' },
  { key: 'concurrent', label: 'Posizioni concorrenti', text: 'Quante posizioni aperte insieme; c’è un limite configurabile.' },
  { key: 'breach', label: 'Breach (violazioni)', text: 'Bandierine quando il prezzo buca lo stop, quando heat/rischio-per-trade/numero posizioni superano i limiti, o quando una deadline si avvicina. Sono flag, non ordini: decidi tu.' },
  { key: 'multiplier', label: 'Moltiplicatore (point value)', text: 'Quanto vale un punto di prezzo per quello strumento. Default 1 (corretto per azioni/crypto); per future/CFD (oro, gas, rame, argento, indici) è diverso — finché non lo imposti in config, rischio e P&L su quegli strumenti sono sottostimati.' },
]
export const RISK_HELP_BY_KEY = byKey(RISK_HELP)

// --- Options terms (desk tooltips + §7) -------------------------------
export const OPTION_HELP = [
  { key: 'call', label: 'Call', text: 'Diritto di comprare il sottostante a un prezzo dato (strike). Sale di valore se il sottostante sale.' },
  { key: 'put', label: 'Put', text: 'Diritto di vendere il sottostante a un prezzo dato (strike). Sale di valore se il sottostante scende.' },
  { key: 'strike', label: 'Strike', text: 'Il prezzo prefissato del contratto.' },
  { key: 'expiry', label: 'Scadenza (expiry)', text: 'La data entro cui l’opzione vale.' },
  { key: 'premium', label: 'Premio', text: 'Il prezzo dell’opzione: quanto paghi (o incassi) per il contratto.' },
  { key: 'bid_ask_mid', label: 'Bid / Ask / Mid', text: 'Prezzo in denaro / in lettera / loro punto medio. Dal mid ricaviamo la volatilità implicita.' },
  { key: 'moneyness', label: 'ITM / ATM / OTM', text: 'In the money (con valore intrinseco) / at the money (strike vicino al prezzo) / out of the money (ancora senza valore intrinseco).' },
  { key: 'oi_volume', label: 'Open Interest / Volume', text: 'Contratti aperti / scambiati nella sessione: indicano liquidità. Alti = prezzi affidabili; bassi = spread larghi e numeri rumorosi.' },
  { key: 'iv', label: 'Volatilità implicita (IV)', text: 'La volatilità che il mercato sconta nel prezzo: quanto si aspetta che il sottostante si muova (in ampiezza, NON in direzione) fino alla scadenza. Ricalcolata da Black-Scholes sul mid (non quella di Yahoo). IV alta = opzioni care.' },
  { key: 'delta', label: 'Delta (Δ)', text: 'Quanto si muove l’opzione per ogni €1 del sottostante; ≈ esposizione equivalente in sottostante.' },
  { key: 'gamma', label: 'Gamma (Γ)', text: 'Quanto velocemente cambia il delta. Alto vicino all’ATM e a ridosso della scadenza.' },
  { key: 'theta', label: 'Theta (Θ)', text: 'Decadimento temporale: quanto valore perde l’opzione ogni giorno. Per chi compra è una perdita (negativo).' },
  { key: 'vega', label: 'Vega', text: 'Quanto si muove il prezzo dell’opzione per ogni punto di IV: la tua esposizione alla volatilità.' },
  { key: 'rho', label: 'Rho (ρ)', text: 'Sensibilità ai tassi d’interesse. Marginale per scadenze brevi.' },
  { key: 'pop', label: 'POP (probabilità di profitto)', text: 'Probabilità che la struttura finisca oltre il breakeven a scadenza, dalla distribuzione implicita nei prezzi (risk-neutral). Sono gli odds impliciti nei prezzi, NON una previsione.' },
  { key: 'payoff', label: 'Payoff', text: 'Profitto/perdita a scadenza al variare del prezzo del sottostante (il grafico).' },
  { key: 'breakeven', label: 'Breakeven', text: 'Il prezzo del sottostante a cui la struttura non guadagna né perde.' },
  { key: 'max_loss_gain', label: 'Max loss / Max gain', text: 'Perdita e guadagno massimi della struttura.' },
  { key: 'rr', label: 'Rischio/rendimento (R:R)', text: 'Rapporto tra guadagno potenziale e perdita massima.' },
  { key: 'single_leg', label: 'Leg singola', text: 'Una sola call o put. Direzionale, semplice.' },
  { key: 'vertical', label: 'Spread verticale', text: 'Compri e vendi due opzioni dello stesso tipo a strike diversi: rischio e guadagno definiti (entrambi limitati).' },
  { key: 'protective_put', label: 'Put protettiva', text: 'Compri una put a copertura di un long che possiedi: mette un pavimento alle perdite, al costo del premio. È un’assicurazione.' },
  { key: 'collar', label: 'Collar', text: 'Put protettiva finanziata vendendo una call: protezione a costo ridotto, in cambio di un tetto ai guadagni.' },
]
export const OPTION_HELP_BY_KEY = byKey(OPTION_HELP)

// --- Decision board terms (M9 tooltips + §9) --------------------------
export const DECISION_HELP = [
  { key: 'ma200', label: 'MA200', text: 'Media mobile a 200 giorni: il riferimento di tendenza di lungo periodo. Sopra = contesto rialzista di fondo, sotto = ribassista. È contesto, non un segnale.' },
  { key: 'rsi', label: 'RSI', text: 'Relative Strength Index (0–100): misura quanto il movimento recente sia stato sbilanciato su o giù. Le soglie qui sono tarate sullo strumento (per l’oro più larghe di 70/30, perché un trend forte tiene l’RSI a lungo agli estremi). “Ipercomprato/ipervenduto” è uno stato di attenzione, NON un segnale di inversione.' },
  { key: 'atr', label: 'ATR', text: 'Average True Range: l’ampiezza media di oscillazione giornaliera (volatilità realizzata). Quanto “respira” lo strumento — utile per dimensionare stop realistici.' },
  { key: 'base_rate', label: 'Base rate (frequenza storica)', text: 'Dato lo streak attuale (es. 5 giorni giù), conta quante volte (n) è già successo nel periodo e cosa è accaduto nei giorni dopo: % di volte in salita e rendimento medio. È la frequenza storica con la sua numerosità, NON una previsione. Con n piccolo non si conclude nulla; se non è mai successo, non viene mostrata alcuna probabilità.' },
  { key: 'pct_up', label: '% in salita', text: 'Frazione delle volte, in passato, in cui dopo questo stesso streak il prezzo era più alto all’orizzonte indicato. Frequenza osservata, da leggere insieme a n — non una probabilità di rimbalzo.' },
  { key: 'implied_prob', label: 'Probabilità implicita', text: 'Probabilità ricavata dai prezzi delle opzioni (risk-neutral, Black-Scholes) che il prezzo finisca sopra/sotto un livello a un dato orizzonte. Sono gli odds del mercato impliciti nei prezzi, NON una previsione.' },
  { key: 'expected_move', label: 'Movimento atteso (±)', text: 'Ampiezza di oscillazione (±1 deviazione standard) che il mercato sconta nelle opzioni fino a quella scadenza, dalla volatilità implicita ATM. In ampiezza, non in direzione.' },
  { key: 'streak', label: 'Streak', text: 'Numero di giorni consecutivi nella stessa direzione. Uno streak lungo è spesso segno di un trend forte, non di un rimbalzo garantito.' },
  { key: 'confluence_read', label: 'Lettura di confluenza', text: 'Quanto le condizioni ATTUALI (driver macro, trend, ecc.) puntano nella stessa direzione per questo strumento. È una fotografia dell’allineamento di oggi, NON una probabilità e NON una previsione del prossimo movimento. Ogni fattore mostra il suo contributo: trasparenza totale.' },
  { key: 'lean', label: 'Lettura direzionale (lean)', text: 'Sintesi pesata dei fattori su scala -100..+100 con un’etichetta (es. “moderatamente ribassista”). NON è una percentuale di salita/discesa: è solo il grado di allineamento delle condizioni attuali. I fattori sono deboli e dipendono dal regime.' },
  { key: 'factor_breakdown', label: 'Dettaglio per fattore', text: 'Ogni fattore con il suo stato (rialzista/ribassista/neutro), tipo (direzionale o contesto) e peso. I fattori di contesto (volatilità, streak, rischio evento) non spingono il lean. Se un dato manca, il fattore è escluso, non indovinato.' },
  { key: 'divergence', label: 'Condizioni ↔ mercato', text: 'Confronta la lettura delle condizioni con la probabilità IMPLICITA nelle opzioni (gli odds del mercato). Se le condizioni sono direzionali ma il mercato è ~neutro, il movimento potrebbe essere già prezzato. L’unica probabilità del futuro resta quella implicita, non la lettura.' },
]
export const DECISION_HELP_BY_KEY = byKey(DECISION_HELP)

// helpers to build definition lists from the keyed dicts (same texts as tooltips)
const dl = (dict, keys) => keys.map((k) => ({ term: dict[k].label, def: dict[k].text }))

// --- Universe (mirrors config.yaml; "why" from brief §4) --------------
export const UNIVERSE_GUIDE = [
  { name: 'Nasdaq 100', symbol: '^NDX', sleeve: 'macro', tradeableOn: 'Fineco (CFD/futures, KO options)', why: 'Aggrega tutta la tesi tech/AI + il macro (Fed, dazi, Cina). Lo strumento più centrale.' },
  { name: 'Gold', symbol: 'GC=F', sleeve: 'macro', tradeableOn: 'Fineco (CFD/futures, KO options)', why: 'Fed, tassi reali, risk-off, incertezza geopolitica/Trump.' },
  { name: 'EUR/USD', symbol: 'EURUSD=X', sleeve: 'macro', tradeableOn: 'Fineco (CFD)', why: 'Espressione più pulita di Fed-contro-ECB. Range intraday contenuto → meglio su catalizzatori/swing.' },
  { name: 'NVIDIA', symbol: 'NVDA', sleeve: 'equity', tradeableOn: 'CFD/equity; opzioni reali via IBKR', why: '(Huang) Bellwether dell’AI; si muove anche sui controlli export verso la Cina.' },
  { name: 'Tesla', symbol: 'TSLA', sleeve: 'equity', tradeableOn: 'CFD/equity; opzioni reali via IBKR', why: '(Musk) Alta volatilità, guidata dalle headline.' },
  { name: 'Alphabet', symbol: 'GOOGL', sleeve: 'equity', tradeableOn: 'CFD/equity; opzioni reali via IBKR', why: '(Pichai) Volatilità più bassa; veicolo da swing/earnings.' },
  { name: 'Copper', symbol: 'HG=F', sleeve: 'commodity', tradeableOn: 'Fineco (CFD/futures, KO options)', why: 'Proxy più pulito della crescita cinese + domanda AI/data-center.' },
  { name: 'DAX 40', symbol: '^GDAXI', sleeve: 'macro', tradeableOn: 'Fineco (CFD/futures, KO options)', why: 'Strumento liquido per la mattina europea prima dell’apertura USA; reagisce a ECB + rischio globale + Cina.' },
  { name: 'Natural Gas (Henry Hub)', symbol: 'NG=F', sleeve: 'energy', tradeableOn: 'Fineco (CFD/futures, KO options)', why: 'Tenuto solo perché ha driver strutturati e tracciabili (storage EIA, meteo, LNG, TTF). Sleeve specialistico, non scommessa nuda sulla volatilità.' },
  { name: 'VIX', symbol: '^VIX', sleeve: 'gauge', traded: false, tradeableOn: 'solo display', why: 'Indicatore di paura/volatilità per temporizzare le coperture. Mostrato, NON tradato (futures/ETP soffrono di decay).' },
]

// --- Glossary (A–Z) ---------------------------------------------------
export const GLOSSARY = [
  { term: 'ATR', body: 'Ampiezza media di oscillazione (volatilità realizzata).' },
  { term: 'ATM / ITM / OTM', body: 'Strike at / in / out of the money.' },
  { term: 'Breakeven', body: 'Prezzo del sottostante a cui una struttura non guadagna né perde.' },
  { term: 'Call / Put', body: 'Diritto di comprare / vendere a strike entro scadenza.' },
  { term: 'Collar', body: 'Put protettiva finanziata da una call venduta (protezione con tetto ai guadagni).' },
  { term: 'CPI / PCE / NFP / PMI', body: 'Inflazione consumi / inflazione cara alla Fed / occupati USA / attività economica.' },
  { term: 'Delta / Gamma / Theta / Vega / Rho', body: 'Sensibilità del prezzo dell’opzione (sottostante, velocità del delta, tempo, volatilità, tassi).' },
  { term: 'FOMC / ECB / EIA', body: 'Riunione Fed / BCE / report scorte gas USA.' },
  { term: 'IV (volatilità implicita)', body: 'Movimento atteso dal mercato, in ampiezza non in direzione.' },
  { term: 'Long / Short', body: 'Posizione al rialzo / al ribasso.' },
  { term: 'MA (20/50/200)', body: 'Medie mobili; la distanza dà il contesto di tendenza.' },
  { term: 'Moltiplicatore / point value', body: 'Valore di un punto di prezzo (1 per azioni/crypto, diverso per future/CFD — da impostare).' },
  { term: 'Open Interest / Volume', body: 'Liquidità di un’opzione.' },
  { term: 'Payoff', body: 'Profitto/perdita a scadenza al variare del sottostante.' },
  { term: 'POP (probabilità di profitto)', body: 'Probabilità implicita nei prezzi oltre il breakeven (odds del mercato, non previsione).' },
  { term: 'Portfolio heat', body: 'Somma dei rischi aperti.' },
  { term: 'Protective put', body: 'Put a copertura di un long posseduto (pavimento alle perdite).' },
  { term: 'R-multiple (R:R)', body: 'Rapporto rischio/rendimento.' },
  { term: 'Rischio per trade', body: 'Perdita se lo stop è colpito, in % del conto.' },
  { term: 'Spread verticale', body: 'Due opzioni stesso tipo, strike diversi: rischio e guadagno definiti.' },
  { term: 'Stop (stop-loss)', body: 'Prezzo di uscita in perdita; definisce il rischio.' },
  { term: 'Strike', body: 'Prezzo prefissato dell’opzione.' },
  { term: 'Base rate', body: 'Frequenza storica di ciò che è successo dopo una certa situazione (es. uno streak), sempre con la sua numerosità n. Non una previsione.' },
  { term: 'RSI', body: 'Relative Strength Index (0–100): sbilanciamento del movimento recente. Soglie tarate per strumento.' },
  { term: 'Probabilità implicita', body: 'Probabilità ricavata dai prezzi delle opzioni (risk-neutral): gli odds del mercato, non una profezia.' },
  { term: 'Tasso reale / Breakeven inflazione', body: 'Driver macro dell’oro da FRED: rendimento decennale al netto dell’inflazione attesa (DFII10) e inflazione attesa a 10 anni (T10YIE).' },
  { term: 'VIX', body: 'Indice della paura (volatilità attesa S&P 500); si guarda, non si tratta.' },
]

// --- Guide sections (0–8). Block types: p | h | ul | dl | note | universe
export const GUIDE_SECTIONS = [
  {
    id: 'uso', label: '0 · Come usarlo', blocks: [
      { type: 'p', text: 'Cos’è. Un centro di comando che mette in un posto solo i dati di mercato, il calendario eventi, le news sintetizzate, gli impatti dei personaggi-chiave, il rischio delle tue posizioni e il desk opzioni. Il suo valore è organizzazione e disciplina: niente ti sfugge, P&L e rischio a colpo d’occhio, le news diventano un briefing corto.' },
      { type: 'p', text: 'Cosa NON è. Non prevede il mercato: le notizie pubbliche sono già nei prezzi in millisecondi. Non ti dà un vantaggio predittivo, ti dà ordine e metodo. Non è consulenza finanziaria. Le decisioni le prendi tu — il cockpit ti mette davanti il contesto e mette alla prova le tue idee contro le tue regole.' },
      { type: 'h', text: 'Un flusso di lavoro tipo' },
      { type: 'ul', items: [
        'Mattino: leggi il briefing ("cosa conta adesso") e i prossimi catalizzatori.',
        'Guarda la watchlist e gli impatti nel key-figures.',
        'Prima di un trade: usa la calcolatrice di sizing e controlla rischio e limiti.',
        'Apri la posizione (dal tuo broker) e registrala nel cockpit + nel journal con la tua tesi.',
        'Per coperture o strutture, usa l’options desk (probabilità implicite, payoff, hedge).',
        'Periodicamente: genera la review del journal per vedere i tuoi pattern.',
      ] },
    ],
  },
  {
    id: 'watchlist', label: '1 · Watchlist & dettaglio', blocks: [
      { type: 'dl', items: [
        { term: 'Δ giornaliera / %', def: 'Variazione del prezzo rispetto alla chiusura precedente, in valuta e in percentuale: il "quanto si è mosso oggi".' },
        { term: 'Distanza dalle MA (20/50/200)', def: 'Di quanto il prezzo è sopra o sotto le medie mobili. Contesto tecnico veloce, non un segnale operativo.' },
        { term: 'ATR (14)', def: 'Average True Range: ampiezza media di oscillazione. Quanto "respira" lo strumento; utile per uno stop realistico (più stretto dell’ATR = colpito dal rumore).' },
        { term: 'VIX', def: 'Indice della paura: volatilità attesa sull’S&P 500. Si guarda, non si tratta (i futures/ETP hanno decadimento). Serve a capire il clima e scegliere i momenti per le coperture.' },
      ] },
      { type: 'h', text: 'Universo strumenti' },
      { type: 'universe' },
    ],
  },
  {
    id: 'calendario', label: '2 · Calendario', blocks: [
      { type: 'dl', items: [
        { term: 'Tipi di evento', def: 'Banche centrali (FOMC = Fed, ECB = BCE), dati USA (CPI, PCE, NFP), dati Cina (PMI), earnings degli strumenti seguiti, EIA (scorte gas, giovedì).' },
        { term: 'Impatto', def: 'Importanza attesa (alto/medio/basso). Gli eventi ad alto impatto possono muovere molto: più cautela su size e stop.' },
        { term: 'Countdown', def: 'Tempo al prossimo evento ad alto impatto. Evita di farti sorprendere "dentro" un trade da un dato che non avevi in mente.' },
      ] },
    ],
  },
  {
    id: 'news', label: '3 · News & briefing', blocks: [
      { type: 'dl', items: [
        { term: 'Temi', def: 'Ogni notizia è etichettata per tema (Fed, UE, Cina, dazi/Trump, NVDA, Google, Musk): filtra il rumore e vede cosa tocca i tuoi strumenti.' },
        { term: 'Briefing mattino / intraday', def: 'Sintesi corta e scannabile ("cosa conta adesso") da news recenti + eventi imminenti + movimenti di prezzo notevoli.' },
        { term: 'Nota di incertezza', def: 'Ogni briefing porta sempre un caveat esplicito. È voluto: la sintesi organizza e riassume, non prevede.' },
      ] },
    ],
  },
  {
    id: 'figure', label: '4 · Key figures', blocks: [
      { type: 'dl', items: [
        { term: 'Chi', def: 'Trump, Powell (Fed), Musk, Jensen Huang, Sundar Pichai, politica cinese.' },
        { term: 'Strumenti impattati', def: 'Per ogni dichiarazione, l’AI indica quali strumenti del tuo universo potrebbero essere mossi.' },
        { term: 'Perché conta', def: 'Una riga di spiegazione, formulata come "possibile influenza", mai come certezza: una mappa di attenzione, non un segnale d’ingresso.' },
      ] },
    ],
  },
  {
    id: 'rischio', label: '5 · Posizioni & rischio', blocks: [
      { type: 'h', text: 'Parametri di una posizione' },
      { type: 'dl', items: dl(FIELD_HELP_BY_KEY, ['symbol', 'side', 'size', 'entry', 'stop', 'target', 'deadline', 'broker', 'thesis']) },
      { type: 'h', text: 'Concetti di rischio' },
      { type: 'dl', items: dl(RISK_HELP_BY_KEY, ['risk_per_trade', 'r_multiple', 'portfolio_heat', 'position_sizing', 'concurrent', 'breach', 'multiplier']) },
      { type: 'h', text: 'Calcolatrice di sizing' },
      { type: 'p', text: 'Inserisci entry, stop e rischio% (e lo strumento, per il moltiplicatore) → ottieni size, rischio aperto e R:R. Usala prima di aprire, per entrare già con la size giusta.' },
    ],
  },
  {
    id: 'journal', label: '6 · Journal', blocks: [
      { type: 'dl', items: [
        { term: 'Campi', def: 'Strumento, tesi, entry/exit, size, stop, esito e — soprattutto — se la tesi si è avverata (sì/no/n.a.), più note. Puoi collegare una posizione e pre-compilare i campi.' },
        { term: 'Esito (outcome)', def: 'Win / loss / breakeven, con P&L.' },
        { term: 'Review AI on demand', def: 'La generi quando vuoi (da worker). Le statistiche le calcola il codice (win rate, R-multiple realizzato, tasso di tesi avverate, P&L); l’AI interpreta i pattern (setup/temi che funzionano, errori ricorrenti).' },
        { term: 'Come leggerla', def: 'È onesta sulla dimensione del campione: con poche voci i pattern sono ipotesi tentative, non conclusioni. Serve a vedere te stesso con i dati alla mano, non a darti un verdetto.' },
      ] },
    ],
  },
  {
    id: 'options', label: '7 · Options desk', blocks: [
      { type: 'p', text: 'Il desk è di SOLA analisi: propone e calcola coperture e strutture, non invia ordini. Tutti i numeri (IV, Greche, probabilità) sono ricalcolati dal codice con Black-Scholes — non si usa la volatilità di Yahoo, inaffidabile.' },
      { type: 'h', text: 'Cosa sono le opzioni' },
      { type: 'dl', items: dl(OPTION_HELP_BY_KEY, ['call', 'put', 'strike', 'expiry', 'premium', 'bid_ask_mid', 'moneyness', 'oi_volume']) },
      { type: 'h', text: 'Volatilità implicita (IV)' },
      { type: 'dl', items: dl(OPTION_HELP_BY_KEY, ['iv']) },
      { type: 'h', text: 'Le Greche (sensibilità del prezzo)' },
      { type: 'dl', items: dl(OPTION_HELP_BY_KEY, ['delta', 'gamma', 'theta', 'vega', 'rho']) },
      { type: 'h', text: 'Probabilità di profitto (POP)' },
      { type: 'note', text: 'La POP è la probabilità implicita nei prezzi (risk-neutral) che la struttura finisca oltre il breakeven. È la quota di una scommessa — reale e implicita nei prezzi — NON una previsione di cosa accadrà.' },
      { type: 'h', text: 'Lettura di una struttura' },
      { type: 'dl', items: dl(OPTION_HELP_BY_KEY, ['payoff', 'breakeven', 'max_loss_gain', 'rr']) },
      { type: 'h', text: 'Le strutture' },
      { type: 'dl', items: dl(OPTION_HELP_BY_KEY, ['single_leg', 'vertical', 'protective_put', 'collar']) },
      { type: 'h', text: 'Modalità del desk' },
      { type: 'dl', items: [
        { term: 'Insurance', def: 'Scegli una holding → il desk propone put/collar con costo, pavimento, breakeven e % di posizione coperta, più il grafico. Per proteggere, non speculare.' },
        { term: 'Directional', def: 'Costruisci una leg singola o uno spread verticale → max loss, R:R, breakeven, POP e payoff. Per valutare un’idea direzionale con i rischi davanti.' },
      ] },
      { type: 'h', text: 'Avvertenze (come fidarti dei numeri)' },
      { type: 'ul', items: [
        'Liquidità: numeri affidabili su contratti liquidi, vicini all’ATM e a scadenza ravvicinata. Su strike sottili l’IV dal mid è rumorosa, e con lei Greche e POP.',
        'Proxy ETF: yfinance dà opzioni solo su azioni/ETF USA. Le macro passano da proxy (Nasdaq→QQQ, oro→GLD, argento→SLV, rame→CPER, gas→UNG): la copertura sulle commodity è un’approssimazione direzionale, non un hedge esatto. Su single-stock è diretta.',
        'Niente opzioni su FX e crypto: non esistono catene su yfinance, compaiono come "no options". È atteso.',
        'Dividendi: Black-Scholes (europea) non li modella: piccola imprecisione sui titoli che pagano dividendi.',
        'Dati ritardati (~15 min): adeguati per swing e coperture; non per scalping sull’ultimo tick.',
      ] },
    ],
  },
  {
    id: 'decision', label: '9 · Decision board', blocks: [
      { type: 'p', text: 'Una vista per strumento (per ora l’oro) che raccoglie in un colpo d’occhio le condizioni che pesi PRIMA di un trade: driver macro, tecnica, una base rate storica onesta e le probabilità implicite nei prezzi delle opzioni. NON è un segnale e NON è una previsione: è il quadro che valuti tu. Il colore indica solo lo stato (favorevole/contrario/attenzione), mai un’azione.' },
      { type: 'h', text: 'Sintesi (lettura di confluenza)' },
      { type: 'dl', items: dl(DECISION_HELP_BY_KEY, ['confluence_read', 'lean', 'factor_breakdown', 'divergence']) },
      { type: 'note', text: 'La lettura è l’allineamento delle condizioni ATTUALI, NON una probabilità: per questo non vedrai mai un “X% sale/scende” calcolato da noi. L’unica probabilità del futuro mostrata è quella IMPLICITA nei prezzi delle opzioni (gli odds del mercato). Il confronto condizioni↔mercato è l’output più utile: se le condizioni puntano da una parte ma il mercato è ~neutro, spesso il movimento è già prezzato.' },
      { type: 'h', text: 'Confluenza' },
      { type: 'p', text: 'Tutte le condizioni con il loro stato: tasso reale ↑/↓, dollaro ↑/↓, streak, posizione vs MA, RSI, ATR, prossimo evento. Favorevole/contrario riflette il contesto storico per quello strumento (es. tasso reale in salita = vento contrario per l’oro), non una raccomandazione.' },
      { type: 'h', text: 'Misure tecniche' },
      { type: 'dl', items: dl(DECISION_HELP_BY_KEY, ['streak', 'ma200', 'rsi', 'atr']) },
      { type: 'h', text: 'Base rate storico (con onestà sul campione)' },
      { type: 'dl', items: dl(DECISION_HELP_BY_KEY, ['base_rate', 'pct_up']) },
      { type: 'note', text: 'Uno streak lungo è spesso il segno di un trend forte, non di un rimbalzo garantito. Mostriamo sempre n: se è troppo piccolo, “campione insufficiente — nessuna conclusione”; se quello streak non si è mai visto, “mai accaduto: nessuna base statistica”, NON una probabilità. La rarità non implica l’inversione.' },
      { type: 'h', text: 'Probabilità implicite dalle opzioni' },
      { type: 'dl', items: dl(DECISION_HELP_BY_KEY, ['implied_prob', 'expected_move']) },
      { type: 'h', text: 'Sintesi AI (opzionale)' },
      { type: 'p', text: 'Quando attiva, mette in parole il setup e segnala le tensioni e l’incertezza. Per regola NON fa mai una chiamata direzionale (sale/scende, compra/vendi): descrive le condizioni, non predice.' },
    ],
  },
  {
    id: 'onesta', label: '10 · Leggere con onestà', blocks: [
      { type: 'p', text: 'Il filo conduttore del cockpit: niente segnali finti.' },
      { type: 'ul', items: [
        'Le probabilità (POP) sono quelle implicite nei prezzi — gli odds del mercato, non profezie.',
        'Le sintesi AI (briefing, key-figures, review) organizzano e segnalano sempre l’incertezza; non dicono cosa succederà.',
        'La parte solida è la disciplina: sizing corretto, limiti di rischio, R:R, countdown delle scadenze, e i tuoi pattern dal journal.',
        '"Cosa apro / come mi comporto" non è un oracolo: è il tuo contesto in ordine e la tua idea messa alla prova contro le tue regole. La decisione resta tua.',
      ] },
    ],
  },
]
