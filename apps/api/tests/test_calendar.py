from datetime import date

import duckdb

from app.data.calendar import get_global_trading_days, get_run_trading_days


def _seed_calendar(con):
    con.execute(
        """
        CREATE TABLE trading_calendars (
            calendar_id VARCHAR,
            name VARCHAR
        );
        """
    )
    con.execute(
        """
        INSERT INTO trading_calendars VALUES
          ('us', 'US'),
          ('in', 'IN');
        """
    )

    con.execute(
        """
        CREATE TABLE calendar_days (
            calendar_id VARCHAR,
            date DATE,
            is_trading_day BOOLEAN
        );
        """
    )
    con.execute(
        """
        INSERT INTO calendar_days VALUES
          ('us', '2024-01-02', TRUE),
          ('us', '2024-01-03', TRUE),
          ('in', '2024-01-02', FALSE),
          ('in', '2024-01-03', TRUE),
          ('in', '2024-01-04', TRUE);
        """
    )

    con.execute(
        """
        CREATE OR REPLACE VIEW calendar_pivot AS
        SELECT
          d.date,
          max(case when c.name = 'US' and d.is_trading_day then 1 else 0 end)::boolean as is_us_trading,
          max(case when c.name = 'IN' and d.is_trading_day then 1 else 0 end)::boolean as is_in_trading,
          max(case when c.name = 'FX' and d.is_trading_day then 1 else 0 end)::boolean as is_fx_trading
        FROM calendar_days d
        JOIN trading_calendars c using (calendar_id)
        GROUP BY 1;
        """
    )

    con.execute(
        """
        CREATE OR REPLACE VIEW global_calendar AS
        SELECT
          date,
          is_us_trading,
          is_in_trading,
          is_fx_trading,
          (is_us_trading or is_in_trading or is_fx_trading) as is_global_trading
        FROM calendar_pivot;
        """
    )

    con.execute(
        """
        CREATE OR REPLACE VIEW global_trading_days AS
        SELECT date
        FROM global_calendar
        WHERE is_global_trading
        ORDER BY date;
        """
    )


def test_global_trading_days_union():
    con = duckdb.connect()
    _seed_calendar(con)

    days = get_global_trading_days(con, date(2024, 1, 2), date(2024, 1, 4))
    assert days == [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]

    con.close()


def test_run_trading_days_union():
    con = duckdb.connect()
    _seed_calendar(con)

    us_only = get_run_trading_days(con, date(2024, 1, 2), date(2024, 1, 4), ["US"])
    both = get_run_trading_days(con, date(2024, 1, 2), date(2024, 1, 4), ["US", "IN"])

    assert us_only == [date(2024, 1, 2), date(2024, 1, 3)]
    assert both == [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 4)]

    con.close()
