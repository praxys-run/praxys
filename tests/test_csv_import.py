"""CSV import provenance tests."""

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.csv_import import _environment_source, import_csvs_for_user
from db.models import Activity, Base, User


def test_environment_source_prefers_explicit_provenance() -> None:
    row = pd.Series({
        "source": "garmin",
        "environment_source": "weather_station_summary",
    })

    assert _environment_source(row, 30.0, 70.0) == "weather_station_summary"


def test_environment_source_uses_connector_and_requires_complete_pair() -> None:
    row = pd.Series({"source": "coros"})

    assert _environment_source(row, 30.0, 70.0) == "coros_activity_summary"
    assert _environment_source(row, 30.0, None) is None


def test_environment_source_preserves_legacy_stryd_overlay() -> None:
    assert (
        _environment_source(pd.Series(dtype=object), 30.0, 70.0)
        == "stryd_activity_weather"
    )


def test_csv_import_excludes_treadmill_environment(tmp_path) -> None:
    """Legacy outdoor weather metadata cannot describe treadmill conditions."""
    stryd_dir = tmp_path / "stryd"
    stryd_dir.mkdir()
    pd.DataFrame([{
        "activity_id": "treadmill-1",
        "date": "2026-07-21",
        "stryd_type": "run",
        "surface_type": "treadmill",
        "temperature_c": 33.4,
        "relative_humidity_pct": 72.0,
        "duration_sec": 3600,
    }]).to_csv(stryd_dir / "power_data.csv", index=False)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(User(
            id="csv-heat-user",
            email="csv-heat@example.com",
            hashed_password="x",
        ))
        db.commit()

        import_csvs_for_user("csv-heat-user", str(tmp_path), db)
        row = db.query(Activity).filter(
            Activity.user_id == "csv-heat-user",
            Activity.activity_id == "treadmill-1",
        ).one()

        assert row.temperature_c is None
        assert row.relative_humidity_pct is None
        assert row.environment_source is None
    finally:
        db.close()
        engine.dispose()
