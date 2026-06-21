// Static reference content for the Guide page and the form tooltips.
// Documentation only — no financial assumptions, no browser storage.
// The universe list mirrors config/config.yaml (§4 of the brief); the
// "why" rationale comes from brief §4. Keep in sync if the universe changes.

// --- Position field help (shared by form tooltips + Guide section a) ---
export const FIELD_HELP = [
  {
    key: 'symbol',
    label: 'Instrument',
    text: 'Lo strumento del trade, scelto dalla tua universe.',
  },
  {
    key: 'side',
    label: 'Side',
    text:
      'Long = al rialzo (guadagni se sale); Short = al ribasso/scoperto ' +
      '(guadagni se scende).',
  },
  {
    key: 'size',
    label: 'Size',
    text:
      'Dimensione della posizione (unità/contratti/azioni o nozionale) — ' +
      'quanto sei esposto.',
  },
  {
    key: 'entry',
    label: 'Entry',
    text: 'Prezzo di ingresso.',
  },
  {
    key: 'stop',
    label: 'Stop',
    text:
      'Stop-loss, prezzo di uscita in perdita per limitare il rischio. ' +
      'Rischio ≈ |entry − stop| × size.',
  },
  {
    key: 'target',
    label: 'Target',
    text: 'Prezzo obiettivo di uscita in profitto.',
  },
  {
    key: 'deadline',
    label: 'Deadline',
    text:
      'Scadenza/orizzonte della posizione (≤3 settimane per lo swing, o ' +
      'expiry dell’opzione); il sistema fa il countdown e avvisa ' +
      'all’avvicinarsi.',
  },
  {
    key: 'broker',
    label: 'Broker',
    text:
      'Dove l’hai aperta (sola registrazione; il cockpit è broker-agnostico).',
  },
  {
    key: 'thesis',
    label: 'Thesis',
    text:
      'La tua tesi, perché hai aperto il trade; servirà al journal per ' +
      'verificare se si è avverata.',
  },
]

// Quick lookup by field key for the form.
export const FIELD_HELP_BY_KEY = Object.fromEntries(
  FIELD_HELP.map((f) => [f.key, f]),
)

// --- Universe (mirrors config.yaml; "why" from brief §4) ---------------
export const UNIVERSE_GUIDE = [
  {
    name: 'Nasdaq 100',
    symbol: '^NDX',
    sleeve: 'macro',
    tradeableOn: 'Fineco (CFD/futures, KO options)',
    why:
      'Aggrega tutta la tesi tech/AI + il macro (Fed, dazi, Cina). Lo ' +
      'strumento più centrale.',
  },
  {
    name: 'Gold',
    symbol: 'GC=F',
    sleeve: 'macro',
    tradeableOn: 'Fineco (CFD/futures, KO options)',
    why: 'Fed, tassi reali, risk-off, incertezza geopolitica/Trump.',
  },
  {
    name: 'EUR/USD',
    symbol: 'EURUSD=X',
    sleeve: 'macro',
    tradeableOn: 'Fineco (CFD)',
    why:
      'Espressione più pulita di Fed-contro-ECB. Range intraday più ' +
      'contenuto → meglio su catalizzatori/swing che in scalping.',
  },
  {
    name: 'NVIDIA',
    symbol: 'NVDA',
    sleeve: 'equity',
    tradeableOn: 'CFD/equity; opzioni reali via IBKR',
    why:
      '(Huang) Bellwether dell’AI; si muove anche sui controlli export ' +
      'verso la Cina.',
  },
  {
    name: 'Tesla',
    symbol: 'TSLA',
    sleeve: 'equity',
    tradeableOn: 'CFD/equity; opzioni reali via IBKR',
    why: '(Musk) Alta volatilità, guidata dalle headline.',
  },
  {
    name: 'Alphabet',
    symbol: 'GOOGL',
    sleeve: 'equity',
    tradeableOn: 'CFD/equity; opzioni reali via IBKR',
    why: '(Pichai) Volatilità più bassa; veicolo da swing/earnings.',
  },
  {
    name: 'Copper',
    symbol: 'HG=F',
    sleeve: 'commodity',
    tradeableOn: 'Fineco (CFD/futures, KO options)',
    why:
      'Proxy più pulito della crescita cinese + domanda AI/data-center.',
  },
  {
    name: 'DAX 40',
    symbol: '^GDAXI',
    sleeve: 'macro',
    tradeableOn: 'Fineco (CFD/futures, KO options)',
    why:
      'Strumento liquido per la mattina europea prima dell’apertura USA; ' +
      'reagisce a ECB + rischio globale + Cina.',
  },
  {
    name: 'Natural Gas (Henry Hub)',
    symbol: 'NG=F',
    sleeve: 'energy',
    tradeableOn: 'Fineco (CFD/futures, KO options)',
    why:
      'Tenuto solo perché ha driver strutturati e tracciabili (sorpresa ' +
      'storage EIA, meteo/degree-days, LNG feedgas, storage vs media 5 anni, ' +
      'TTF/storage UE). Sleeve specialistico, non una scommessa nuda sulla ' +
      'volatilità.',
  },
  {
    name: 'VIX',
    symbol: '^VIX',
    sleeve: 'gauge',
    traded: false,
    tradeableOn: 'solo display',
    why:
      'Indicatore di paura/volatilità per temporizzare le coperture. ' +
      'Mostrato, NON tradato direttamente (futures/ETP soffrono di decay).',
  },
]

// --- Risk concepts (Guide section b) -----------------------------------
export const RISK_CONCEPTS = [
  {
    title: 'Rischio per trade',
    body:
      'Quanto capitale metti a rischio su una singola operazione: ' +
      '≈ |entry − stop| × size. Di norma si esprime come % del conto ' +
      '(es. 1%). È l’importo che perdi se viene colpito lo stop.',
  },
  {
    title: 'R-multiple (rischio/rendimento)',
    body:
      'L’unità “R” è il rischio iniziale del trade. Un guadagno di 2R vale ' +
      'due volte il rischio; una perdita piena è −1R. Misura il ' +
      'rischio/rendimento in modo indipendente dalla size: target e stop ' +
      'definiscono l’R atteso (es. target a 3R).',
  },
  {
    title: 'Portfolio heat',
    body:
      'La somma del rischio aperto su tutte le posizioni contemporaneamente. ' +
      'Se ogni trade rischia 1% e ne hai 5 aperti, l’heat è ~5%. Serve a ' +
      'non concentrare troppo rischio simultaneo.',
  },
  {
    title: 'Position sizing',
    body:
      'Dato il rischio per trade (in valuta) e la distanza entry→stop, la ' +
      'size = rischio / |entry − stop|. Così rischi un importo costante a ' +
      'prescindere da dove metti lo stop.',
  },
  {
    title: 'Il clock a 3 settimane',
    body:
      'Per gli swing la deadline è ≤3 settimane (o l’expiry dell’opzione). ' +
      'Il cockpit fa il countdown e avvisa all’avvicinarsi, così una tesi a ' +
      'termine non resta aperta oltre il suo orizzonte.',
  },
]

export const RISK_PHASE_NOTE =
  'La calcolatrice di position sizing e i limiti di rischio (max rischio per ' +
  'trade, heat massimo, numero massimo di posizioni) arrivano in Fase 3 (M6). ' +
  'Qui trovi solo i concetti: nessun calcolo automatico è ancora attivo.'

// --- Stats glossary (Guide section d) ----------------------------------
export const GLOSSARY = [
  {
    term: 'ATR (Average True Range)',
    body:
      'Misura il range/volatilità media giornaliera su N sedute (qui ' +
      'ATR14). Più alto = movimenti più ampi. Utile per dimensionare gli ' +
      'stop e capire l’ampiezza tipica del movimento.',
  },
  {
    term: 'Distanza dalle MA (MA20/50/200)',
    body:
      'Scostamento percentuale del prezzo dalla sua media mobile semplice a ' +
      '20/50/200 sedute. Positivo = prezzo sopra la media (forza relativa di ' +
      'breve/medio/lungo periodo); aiuta a leggere trend ed estensione.',
  },
  {
    term: 'Variazione giornaliera Δ / %',
    body:
      'Differenza assoluta (Δ) e percentuale tra l’ultima chiusura e quella ' +
      'precedente.',
  },
  {
    term: 'VIX (indice della paura)',
    body:
      'Volatilità implicita attesa a 30 giorni sull’S&P 500. Sale quando ' +
      'cresce l’incertezza/risk-off. Nel cockpit è un gauge per temporizzare ' +
      'le coperture, non uno strumento tradato.',
  },
]
