"""Resilient insert — a stored calibration must survive schema drift (a migration
not yet applied). PostgREST rejects the whole row when a column is unknown; the
storage layer drops that column and retries so results/weights still persist."""
import pytest

from app.storage.supabase_storage import SupabaseStorage


class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    """Records the last inserted payload; raises PGRST204-style errors for any
    column named in `missing` until it has been dropped from the payload."""
    def __init__(self, missing):
        self.missing = set(missing)
        self.last_payload = None

    def insert(self, row):
        self.last_payload = dict(row)
        return self

    def execute(self):
        for col in self.missing:
            if col in self.last_payload:
                raise RuntimeError(
                    f"Could not find the '{col}' column of 'calibrations' in the schema cache")
        return _FakeResult([self.last_payload])


class _FakeClient:
    def __init__(self, missing):
        self._table = _FakeTable(missing)

    def table(self, _name):
        return self._table


def _storage(missing):
    st = object.__new__(SupabaseStorage)          # bypass create_client()
    st._client = _FakeClient(missing)
    return st, st._client._table


def test_insert_drops_unknown_column_and_persists_the_rest():
    st, table = _storage(missing={"weight_horizon"})
    row = {"test_count": 462, "weight_horizon": 5, "results": {"GC=F": {}}}
    out = st._insert_resilient("calibrations", row)
    assert "weight_horizon" not in table.last_payload   # dropped
    assert out["test_count"] == 462                       # everything else kept
    assert out["results"] == {"GC=F": {}}


def test_insert_passes_through_when_schema_matches():
    st, table = _storage(missing=set())
    row = {"test_count": 1, "weight_horizon": 5}
    out = st._insert_resilient("calibrations", row)
    assert out == row                                     # nothing dropped


def test_insert_reraises_non_column_errors():
    st = object.__new__(SupabaseStorage)

    class _Boom:
        def table(self, _n):
            return self

        def insert(self, _r):
            return self

        def execute(self):
            raise RuntimeError("network unreachable")

    st._client = _Boom()
    with pytest.raises(RuntimeError, match="network unreachable"):
        st._insert_resilient("calibrations", {"a": 1})
