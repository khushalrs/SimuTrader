-- Calendar views for DuckDB (expects calendar_days + trading_calendars views or tables)

CREATE OR REPLACE VIEW calendar_pivot AS
SELECT
  d.date,
  max(case when c.name = 'US' and d.is_trading_day then 1 else 0 end)::boolean as is_us_trading,
  max(case when c.name = 'IN' and d.is_trading_day then 1 else 0 end)::boolean as is_in_trading,
  max(case when c.name = 'FX' and d.is_trading_day then 1 else 0 end)::boolean as is_fx_trading
FROM calendar_days d
JOIN trading_calendars c using (calendar_id)
GROUP BY 1;

CREATE OR REPLACE VIEW global_calendar AS
SELECT
  date,
  is_us_trading,
  is_in_trading,
  is_fx_trading,
  (is_us_trading or is_in_trading or is_fx_trading) as is_global_trading
FROM calendar_pivot;

CREATE OR REPLACE VIEW global_trading_days AS
SELECT date
FROM global_calendar
WHERE is_global_trading
ORDER BY date;
