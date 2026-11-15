-- One row per day. MetricFlow needs this to work with dates.
select cast(d as date) as date_day
from generate_series(date '2015-01-01', date '2031-12-31', interval 1 day) as t(d)
