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
  { key: 'risk_per_trade', label: 'Rischio per trade', text: 'Quanto perdi se lo stop viene colpito, in valuta e come % del conto. Il valore predefinito (es. 1–2%) arriva dal file di configurazione (config.yaml → risk.max_risk_per_trade_pct): il cockpit è read-only, non c’è una schermata impostazioni. Puoi comunque digitare una % diversa direttamente nel campo “Rischio %”.' },
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
  { key: 'ov_divergence', label: 'Divergenza (panoramica)', text: 'Quanto la lettura delle CONDIZIONI (la lancetta di confluenza, riportata a −1..+1) si discosta dal lean del MERCATO ricavato dagli odds impliciti (= (prob. salita − 0,5)×2). È un numero 0–2: più alto = condizioni e mercato sono più in disaccordo (≥0,60 è evidenziato). Serve a decidere DOVE GUARDARE — dove approfondire la tensione — NON è una probabilità di successo né un segnale. L’unica probabilità del futuro resta quella implicita.' },
  { key: 'ov_last', label: 'Ultimo', text: 'Ultimo prezzo noto dello strumento (dall’ultimo aggiornamento dati). Non in tempo reale al tick.' },
  { key: 'ov_next_event', label: 'Prossimo evento', text: 'Il prossimo catalizzatore in calendario per lo strumento, col conto alla rovescia. Ordinando per “Evento” metti in cima ciò che è più vicino. Vicino a un evento la lettura di condizioni può ribaltarsi.' },
  { key: 'breakeven_winrate', label: 'Win-rate di pareggio', text: 'La frazione di volte in cui devi aver ragione SOLO per non perdere soldi, costi inclusi: (rischio + costi) / (rischio + reward). Con R/R 3 è ~25% senza costi, di più con i costi. Confrontalo con gli odds impliciti: batterli richiede una TESI, non è garantito. Nessun EV previsto.' },
  { key: 'seasonality', label: 'Ciclicità (stagionalità)', text: 'Pattern ricorrenti nel calendario: rendimento medio per mese e per giorno della settimana, con n SEMPRE visibile. La stagionalità è il regno del data-snooping: con abbastanza fette temporali qualcosa sembra sempre ciclico. Sotto la soglia di campione → “insufficiente”, nessuna conclusione. Il flag |t|>2 non corregge i test multipli. È frequenza storica, NON una previsione.' },
]
export const DECISION_HELP_BY_KEY = byKey(DECISION_HELP)

// --- Backtest / research terms (tooltips + §10) -----------------------
export const BACKTEST_HELP = [
  { key: 'oos', label: 'Out-of-sample', text: 'I dati NON usati per scegliere la regola/parametri. È l’unico test onesto: se la regola funziona solo in-sample (sui dati su cui è stata tarata) ma crolla out-of-sample, era overfitting. Qui mostriamo l’out-of-sample in primo piano.' },
  { key: 'degradation', label: 'Degrado IS→OOS', text: 'Quanto una metrica (es. lo Sharpe) cala dall’in-sample all’out-of-sample. Un calo forte è il segnale tipico di overfitting; poco calo = più robusta (mai una garanzia).' },
  { key: 'sharpe', label: 'Sharpe ratio', text: 'Rendimento per unità di rischio (volatilità), annualizzato. Più alto = meglio a parità di rischio. Sempre calcolato al NETTO dei costi.' },
  { key: 'delta_bh', label: 'vs Buy&Hold', text: 'Differenza di rendimento NETTO tra la strategia e il semplice comprare-e-tenere lo stesso strumento. Se la strategia non batte il buy-and-hold netto, non aggiunge valore.' },
  { key: 'bootstrap', label: 'Bootstrap', text: 'Ricampiona molte volte i rendimenti per stimare un intervallo di confidenza (non un singolo numero) e quanto spesso la strategia NON batte la fortuna o il buy-and-hold. Se la CI dello Sharpe include 0, non è distinguibile dal caso.' },
  { key: 'p_luck', label: 'P(non > fortuna)', text: 'Frazione dei ricampionamenti in cui lo Sharpe è ≤ 0: quanto è plausibile che il risultato sia solo fortuna. Alta = poco affidabile.' },
  { key: 'deflated', label: 'Sharpe deflazionato (DSR)', text: 'Correzione per test multipli (Bailey & López de Prado): cercando tra N combinazioni, il MIGLIORE è atteso sembrare buono per puro caso. Il DSR sconta questo numero di tentativi e la non-normalità dei rendimenti. DSR alto (>0.95) = robusto; basso = probabile illusione da data-snooping.' },
  { key: 'consistency', label: 'Coerenza multi-strumento', text: 'La STESSA regola eseguita su tutto l’universo. Un edge vero appare su più strumenti, non su uno solo in una finestra fortunata.' },
  { key: 'costs', label: 'Costi & slippage', text: 'Commissioni + spread + slippage dedotti ad ogni trade (in bps, configurabili). I risultati NETTI sono quelli che contano: lordi gonfiano sempre.' },
]
export const BACKTEST_HELP_BY_KEY = byKey(BACKTEST_HELP)

// --- FX desk signals (EUR/USD tooltips + §9) --------------------------
export const FX_HELP = [
  { key: 'skew', label: 'Skew / Risk reversal', text: 'Risk reversal a 25 delta = IV(put 25Δ) − IV(call 25Δ), interpolata dalla smile (proxy FXE). Positivo = put più care = bias ribassista (dove si concentrano flussi e coperture); negativo = bias rialzista. È dove si concentra il mercato, NON una previsione. Se la smile è rada, l’affidabilità è bassa e non pesa nel lean.' },
  { key: 'expected_move_event', label: 'Movimento atteso (evento)', text: 'Il movimento ±% che il mercato prezza nelle opzioni fino alla scadenza che abbraccia il prossimo evento (FOMC/BCE/CPI/NFP). È un’ampiezza, NON una direzione.' },
  { key: 'event_behaviour', label: 'Comportamento storico evento', text: 'Per gli eventi passati dello stesso tipo: movimento assoluto mediano nel giorno e quante volte il primo movimento è PROSEGUITO vs si è INVERTITO nei giorni dopo, con n sempre visibile. Frequenza storica, non una previsione; sotto soglia → "campione insufficiente".' },
  { key: 'cot', label: 'Posizionamento COT', text: 'Posizione netta dei Leveraged Funds (COT della CFTC) sul future EUR, come percentile su ~3 anni. >90° = molto long → rischio reversal; <10° = molto short → rischio squeeze; in mezzo poco segnale. Ritardo martedì→venerdì, utile come contrarian solo agli estremi, segnale di swing non intraday.' },
]
export const FX_HELP_BY_KEY = byKey(FX_HELP)

// --- "Quadro completo" (single stocks): one tip per factor chip -------
// Keys MUST match the factor keys emitted by worker full_picture.py.
export const FULLPIC_HELP = [
  { key: 'valuation', label: 'Valutazione', text: 'Quanto paghi l’azienda: P/E (prezzo/utili), P/S (prezzo/ricavi), P/B (prezzo/patrimonio), e dove sta il P/E rispetto alla propria storia (percentile). “Cara/economica” è descrittivo — già riflesso nel prezzo — NON una direzione da seguire.' },
  { key: 'growth', label: 'Crescita', text: 'Variazione anno-su-anno di ricavi e utili. In crescita/in calo è un fatto sull’azienda, non una previsione del prezzo.' },
  { key: 'quality', label: 'Qualità', text: 'Redditività dell’azienda: margine netto e ROE (return on equity). Margini alti/ROE alto = azienda più efficiente; è contesto, non un segnale.' },
  { key: 'cash', label: 'Cassa / bilancio', text: 'Solidità finanziaria: free cash flow (cassa generata al netto degli investimenti) e debt/equity (debito rispetto al patrimonio). FCF positivo e poco debito = più solida.' },
  { key: 'earnings_risk', label: 'Rischio utili', text: 'Giorni al prossimo report trimestrale + storico delle sorprese (beat/miss). Vicino agli utili la volatilità sale e la lettura di condizioni può ribaltarsi.' },
  { key: 'macro', label: 'Contesto macro (sfondo)', text: 'Il lean dei SOLI driver macro (tassi, VIX) per il titolo. Per un’azione è sfondo: conta più l’azienda e la notizia.' },
  { key: 'technical', label: 'Contesto tecnico (sfondo)', text: 'Posizione rispetto alle medie mobili, RSI e streak. Contesto debole: un movimento esteso spesso CONTINUA, non si inverte.' },
  { key: 'skew', label: 'Skew (opzioni)', text: 'Skew / risk reversal delle opzioni: confronta il costo (volatilità implicita) delle PUT contro le CALL sullo stesso titolo. Put più care = bias ribassista (dove si concentrano coperture e flussi); call più care = bias rialzista. Indica DOVE si posiziona il mercato delle opzioni, NON è una previsione; se la smile è rada è poco affidabile e non pesa nel lean.' },
]
export const FULLPIC_HELP_BY_KEY = byKey(FULLPIC_HELP)

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
      { type: 'h', text: 'Gate pre-trade (checklist "Nuovo trade")' },
      { type: 'p', text: 'Prima di registrare una posizione, la checklist calcola rischio €/% (col point value corretto), R/R, heat risultante e n° posizioni, mostra la lettura macro del decision board (con o contro la marea) e produce WARNING chiari quando un numero sfora le tue regole: rischio per trade, heat, posizioni concorrenti, R/R sotto soglia, evento ad alto impatto imminente. I warning NON bloccano — il cockpit è read-only, decidi tu. Alla conferma registra la posizione e crea in automatico una bozza di journal collegata. Il colore indica solo la severità.' },
      { type: 'note', text: 'Il gate valida DISCIPLINA e RISCHIO, non la direzione: non dà probabilità direzionali né dice "buon/cattivo trade". Mette i tuoi numeri davanti alle tue regole.' },
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
      { type: 'p', text: 'Disponibile per più strumenti (seleziona in alto): i driver cambiano per strumento. Per l’oro contano tasso reale, dollaro e VIX; per EUR/USD il driver chiave è il DIFFERENZIALE di tassi Fed-BCE (Fed funds − tasso deposito BCE): se si stringe, tende a sostenere l’euro; per il Nasdaq il driver chiave è il TASSO (duration) — il tasso reale a 10y giù sostiene i tech a lunga durata — mentre la tesi passa da news/key-figure (Huang, Pichai, Musk) e dagli utili dei mega-cap, non da una singola serie macro. Le soglie RSI sono tarate per strumento (oro più larghe, EUR/USD e Nasdaq standard 30/70). Nota: per gli indici azionari il COT è un segnale debole (lo skew QQQ è il read di posizionamento migliore).' },
      { type: 'h', text: 'Sintesi (lettura di confluenza)' },
      { type: 'dl', items: dl(DECISION_HELP_BY_KEY, ['confluence_read', 'lean', 'factor_breakdown', 'divergence']) },
      { type: 'note', text: 'La lettura è l’allineamento delle condizioni ATTUALI, NON una probabilità: per questo non vedrai mai un “X% sale/scende” calcolato da noi. L’unica probabilità del futuro mostrata è quella IMPLICITA nei prezzi delle opzioni (gli odds del mercato). Il confronto condizioni↔mercato è l’output più utile: se le condizioni puntano da una parte ma il mercato è ~neutro, spesso il movimento è già prezzato.' },
      { type: 'h', text: 'Panoramica strumenti (schermata Mercati)' },
      { type: 'p', text: 'La tabella “Strumenti — panoramica” mette a confronto tutti gli strumenti in un colpo d’occhio e si ordina per DOVE GUARDARE, non per “probabilità di successo”. Ogni colonna ha la sua spiegazione (icona i). Colonne: Ultimo prezzo · Confluenza (lancetta delle condizioni) · Prob. salita (implicita, calibrata) · Movimento atteso (±) · Divergenza · prossimo Evento.' },
      { type: 'dl', items: dl(DECISION_HELP_BY_KEY, ['ov_divergence', 'ov_last', 'ov_next_event']) },
      { type: 'h', text: 'Confluenza' },
      { type: 'p', text: 'Tutte le condizioni con il loro stato: tasso reale ↑/↓, dollaro ↑/↓, streak, posizione vs MA, RSI, ATR, prossimo evento. Favorevole/contrario riflette il contesto storico per quello strumento (es. tasso reale in salita = vento contrario per l’oro), non una raccomandazione.' },
      { type: 'h', text: 'Misure tecniche' },
      { type: 'dl', items: dl(DECISION_HELP_BY_KEY, ['streak', 'ma200', 'rsi', 'atr']) },
      { type: 'h', text: 'Base rate storico (con onestà sul campione)' },
      { type: 'dl', items: dl(DECISION_HELP_BY_KEY, ['base_rate', 'pct_up']) },
      { type: 'note', text: 'Uno streak lungo è spesso il segno di un trend forte, non di un rimbalzo garantito. Mostriamo sempre n: se è troppo piccolo, “campione insufficiente — nessuna conclusione”; se quello streak non si è mai visto, “mai accaduto: nessuna base statistica”, NON una probabilità. La rarità non implica l’inversione.' },
      { type: 'h', text: 'Probabilità implicite dalle opzioni' },
      { type: 'dl', items: dl(DECISION_HELP_BY_KEY, ['implied_prob', 'expected_move']) },
      { type: 'h', text: 'Segnali FX da desk (EUR/USD)' },
      { type: 'dl', items: dl(FX_HELP_BY_KEY, ['skew', 'expected_move_event', 'event_behaviour', 'cot']) },
      { type: 'h', text: 'Quadro completo (titoli singoli)' },
      { type: 'p', text: 'Per NVDA/TSLA/GOOGL il board mostra un “quadro completo” con tutti i fattori affiancati, ognuno col suo stato — NON sommati in un punteggio. Il numero integrato di tutto-insieme è la probabilità implicita; l’integrazione qualitativa è l’analisi AI.' },
      { type: 'dl', items: dl(FULLPIC_HELP_BY_KEY, ['valuation', 'growth', 'quality', 'cash', 'earnings_risk', 'macro', 'technical', 'skew']) },
      { type: 'h', text: 'Sintesi AI (opzionale)' },
      { type: 'p', text: 'Quando attiva, mette in parole il setup e segnala le tensioni e l’incertezza. Per regola NON fa mai una chiamata direzionale (sale/scende, compra/vendi): descrive le condizioni, non predice.' },
    ],
  },
  {
    id: 'backtest', label: '10 · Ricerca / Backtest', blocks: [
      { type: 'p', text: 'Un banco di ricerca per MISURARE se una regola tecnica ha davvero un vantaggio (edge) — NON un generatore di segnali. È costruito apposta per rendere VISIBILE l’overfitting, non per nasconderlo. I run si lanciano dal worker (CLI) e si leggono qui.' },
      { type: 'p', text: 'Nessun look-ahead: il segnale al giorno t usa solo dati fino alla chiusura di t, e l’ingresso avviene all’apertura di t+1 (mai sulla stessa barra che ha generato il segnale). I costi (commissioni+spread+slippage) sono SEMPRE dedotti: contano i risultati NETTI, confrontati col buy-and-hold netto.' },
      { type: 'h', text: 'Le salvaguardie anti-illusione' },
      { type: 'dl', items: dl(BACKTEST_HELP_BY_KEY, ['oos', 'degradation', 'costs', 'consistency', 'deflated', 'bootstrap']) },
      { type: 'note', text: 'Cercando tra molti parametri/regole, il MIGLIORE è atteso sembrare buono per puro caso. Per questo mostriamo la distribuzione di TUTTI i tentativi, il loro numero, e lo Sharpe deflazionato — mai il best-of-N spacciato per edge. E il dato che conta è l’out-of-sample netto, non l’in-sample.' },
      { type: 'h', text: 'Metriche' },
      { type: 'dl', items: dl(BACKTEST_HELP_BY_KEY, ['sharpe', 'delta_bh', 'p_luck']) },
      { type: 'h', text: 'Le regole testabili' },
      { type: 'ul', items: [
        'Crossover di medie (es. 50/200) con filtro di trend.',
        'RSI mean-reversion (compra ipervenduto, esci ipercomprato).',
        'Breakout di canale (Donchian, max/min a N giorni).',
        'Mean-reversion su streak: "compra dopo N giorni giù, tieni M giorni" (la regola "5 giù → rimbalza").',
        'Reversione su Bollinger.',
      ] },
    ],
  },
  {
    id: 'teoria', label: '11 · Teoria & fonti', blocks: [
      { type: 'p', text: 'Per ogni dato: COS’È · PERCHÉ conta / come si legge · la TEORIA · i CAVEAT. Tono didattico: l’onestà è parte del metodo.' },
      { type: 'h', text: 'Cosa muove ogni strumento (e via quale fonte)' },
      { type: 'dl', items: [
        { term: 'Oro (GC=F)', def: 'Tasso reale 10y (DFII10) e dollaro (DTWEXBGS) da FRED; VIX come clima. Teoria: l’oro non rende cedole, quindi compete col rendimento reale dei Treasury — tasso reale ↑ = costo-opportunità ↑. Caveat: relazione storica, non legge fisica.' },
        { term: 'EUR/USD', def: 'Driver principale: differenziale tassi Fed-BCE (DFEDTARU − ECBDFR, FRED). Teoria: il carry e i flussi seguono il differenziale di policy. Caveat: conta anche il rischio globale e i flussi, non solo i tassi.' },
        { term: 'Nasdaq (^NDX)', def: 'Tasso reale (duration dei tech) + spread HY (condizioni finanziarie) + VIX; la tesi vera arriva da news/utili mega-cap. Teoria: i cash-flow lontani sono molto sensibili al tasso di sconto.' },
        { term: 'Azioni singole (NVDA/TSLA/GOOGL)', def: 'Driver = narrativa del titolo (news/key-figure) ed EARNINGS; la macro è solo sfondo. Lo skew delle opzioni del titolo è il read di posizionamento (no COT sui singoli).' },
        { term: 'Rame (HG=F)', def: 'Crescita Cina + domanda industriale (via PMI/news, non una serie FRED pulita); dollaro come contesto. COT (Managed Money) utile, contrarian agli estremi.' },
        { term: 'DAX (^GDAXI)', def: 'BCE + rischio globale + Cina (esportatori) + euro. Opzioni Eurex non su yfinance → proxy ETF approssimato (implicite a bassa affidabilità). Niente COT (Eurex non è CFTC).' },
      ] },
      { type: 'h', text: 'Probabilità implicita (l’unico numero calibrato)' },
      { type: 'note', text: 'È la probabilità RISK-NEUTRAL estratta dai prezzi delle opzioni: incorpora in tempo reale ciò che il mercato sconta, quindi è l’unica “calibrata”. ATM ≈ 50/50 perché a breve il drift è trascurabile rispetto alla volatilità. Il movimento atteso = IV×√T. Caveat: risk-neutral ≠ probabilità “reale”; include un premio per il rischio.' },
      { type: 'h', text: 'Base rate (frequenza storica)' },
      { type: 'note', text: 'Conta quante volte (n) una situazione si è ripetuta e cosa è successo dopo. Mostriamo SEMPRE n: con n piccolo non si conclude nulla. Fallacia dello scommettitore: dopo 5 ribassi non è “dovuto” un rimbalzo — uno streak lungo è spesso segno di trend, non di inversione.' },
      { type: 'h', text: 'Tecnica = contesto, non segnale' },
      { type: 'dl', items: [
        { term: 'MA 200/50', def: 'Riferimenti di tendenza. Teoria: catturano la persistenza dei trend; l’evidenza accademica sul time-series momentum è mista e dipende dal regime/costi. Contesto, non un trigger.' },
        { term: 'RSI', def: 'Sbilanciamento recente con soglie tarate per strumento (non 70/30 ovunque). “Ipercomprato” in un trend forte può restarci a lungo: stato di attenzione, non inversione.' },
        { term: 'ATR', def: 'Volatilità realizzata: serve a dimensionare stop realistici, non a prevedere la direzione.' },
      ] },
      { type: 'h', text: 'Segnali da desk' },
      { type: 'ul', items: [
        'Skew / risk reversal: dove si concentrano coperture/flussi (lean prezzato), NON una previsione; su smile rade = bassa affidabilità.',
        'Expected-move sugli eventi: magnitudo che il mercato prezza fino alla scadenza che abbraccia l’evento — ampiezza, non direzione.',
        'COT: posizionamento; utile come CONTRARIAN solo agli estremi del percentile; debole sugli indici azionari (meglio lo skew); ritardo martedì→venerdì.',
      ] },
      { type: 'h', text: 'Lettura di confluenza (la lancetta)' },
      { type: 'note', text: 'Somma pesata dello stato dei fattori su −100..+100: è l’ALLINEAMENTO delle condizioni attuali, NON una probabilità e NON un segnale compra/vendi. Per questo non vedrai mai un “X% sale” fabbricato: la probabilità resta quella implicita.' },
      { type: 'h', text: 'Gestione del rischio & eventi' },
      { type: 'ul', items: [
        'L’edge sostenibile sta in COME scommetti: sizing corretto, R:R, limiti di heat, scadenze — più che nell’indovinare la direzione.',
        'Eventi: il primo movimento spesso si inverte; usa countdown + rischio-evento + strutture a rischio definito (opzioni) per non farti sorprendere "dentro" un trade.',
      ] },
    ],
  },
  {
    id: 'onesta', label: '12 · Leggere con onestà', blocks: [
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
