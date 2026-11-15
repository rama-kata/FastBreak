-- One row per team per game: each game appears twice, once from each side.
with sides as (
    select game_id, season, season_type, game_date, is_neutral, overtimes,
           home_team_id as team_id, away_team_id as opponent_id,
           'home' as home_away, home_pts as points, away_pts as opponent_points
    from {{ ref('stg_games') }}
    union all
    select game_id, season, season_type, game_date, is_neutral, overtimes,
           away_team_id, home_team_id,
           'away', away_pts, home_pts
    from {{ ref('stg_games') }}
)
select
    s.game_id,
    s.game_date,
    s.season,
    s.season_type,
    s.team_id,
    t.team_abbr,
    s.opponent_id,
    o.team_abbr as opponent_abbr,
    s.home_away,
    s.is_neutral,
    s.points,
    s.opponent_points,
    s.points - s.opponent_points as margin,
    s.points > s.opponent_points as won,
    s.overtimes
from sides s
join {{ ref('dim_teams') }} t on t.team_id = s.team_id
join {{ ref('dim_teams') }} o on o.team_id = s.opponent_id
