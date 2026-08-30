"""ToneProvider: too little text -> "non valutabile" (never invented); with text
it returns a QUALITATIVE reading and NEVER a directional number. Fake AI client."""
import json

from app.providers.tone import HaikuToneProvider, TONE_LABEL


class _FakeAI:
    def __init__(self, resp):
        self.resp = resp
        self.called = False

    def json_call(self, **kwargs):
        self.called = True
        return self.resp


def test_missing_text_is_not_evaluable_and_does_not_call_ai():
    ai = _FakeAI(None)
    tp = HaikuToneProvider(ai, "haiku")
    r = tp.read_quarter("MSFT", "2026-Q2", [{"title": "x", "body": "short"}])
    assert r["evaluable"] is False
    assert "non valutabile" in r["note"]
    assert ai.called is False                       # gated before any AI cost


def test_reading_is_qualitative_no_number():
    ai = _FakeAI({
        "guidance": "confermata", "caution_confidence": "più fiducioso",
        "summary": "Linguaggio più sicuro sul cloud; toni prudenti sul consumer.",
        "changes_vs_prior": "Meno cautela sui margini rispetto al trimestre prima.",
        "themes_new": ["AI capex"], "themes_gone": ["layoffs"],
    })
    tp = HaikuToneProvider(ai, "haiku")
    texts = [{"title": "Q2 earnings release", "source": "IR",
              "body": "x" * 500, "date": "2026-07-30"}]
    r = tp.read_quarter("MSFT", "2026-Q2", texts, prior={"period_label": "2026-Q1", "summary": "prima"})
    assert r["evaluable"] is True
    assert r["guidance"] == "confermata" and r["caution_confidence"] == "più fiducioso"
    assert r["note"] == TONE_LABEL
    assert r["sources"][0]["title"] == "Q2 earnings release"
    # NO numeric/directional score anywhere in the reading
    blob = json.dumps(r, ensure_ascii=False).lower()
    assert "salir" not in blob and "scender" not in blob
    # no numeric score (bool `evaluable` excluded — it's a flag, not a score)
    assert not any(isinstance(v, (int, float)) and not isinstance(v, bool) for v in r.values())


def test_ai_failure_degrades_to_not_evaluable():
    tp = HaikuToneProvider(_FakeAI(None), "haiku")
    r = tp.read_quarter("MSFT", "2026-Q2", [{"title": "t", "body": "y" * 600, "source": "IR"}])
    assert r["evaluable"] is False and "non valutabile" in r["note"]


class _ToneStore:
    def __init__(self):
        self.transcripts = {}
        self.tone = {}

    def get_fundamentals_history(self, symbol, limit):
        return [{"period_end": "2026-06-30", "period_label": "2026-Q2"},
                {"period_end": "2026-03-31", "period_label": "2026-Q1"}]

    def get_tone_reading(self, symbol, period_end):
        return self.tone.get((symbol, period_end))

    def upsert_transcript(self, row):
        self.transcripts[(row["symbol"], row["period_end"])] = row
        return row

    def upsert_tone_reading(self, row):
        self.tone[(row["symbol"], row["period_end"])] = row
        return row


def test_user_transcript_makes_tone_evaluable():
    from app.ingestion.fundamentals_job import read_tone_from_transcript
    ai = _FakeAI({"guidance": "alzata", "caution_confidence": "più fiducioso",
                  "summary": "Toni molto positivi sul cloud e sull'AI.",
                  "themes_new": ["AI"], "themes_gone": []})
    tp = HaikuToneProvider(ai, "haiku")
    st = _ToneStore()
    out = read_tone_from_transcript(st, tp, "MSFT", "x" * 4000)   # full transcript text
    assert out["period_end"] == "2026-06-30" and out["period_label"] == "2026-Q2"
    assert out["reading"]["evaluable"] is True
    # transcript persisted + tone reading upserted for the latest quarter
    assert ("MSFT", "2026-06-30") in st.transcripts
    stored = st.tone[("MSFT", "2026-06-30")]
    assert stored["evaluable"] is True and stored["guidance"] == "alzata"
