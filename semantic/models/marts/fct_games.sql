-- One row per game. Count games here, not in fct_team_games, which has two rows a game.
select
    g.game_id,
    g.game_date,
    g.season,
    g.season_type,
    h.team_abbr as home_abbr,
    a.team_abbr as away_abbr,
    g.home_pts,
    g.away_pts,
    case when g.home_pts > g.away_pts then h.team_abbr else a.team_abbr end as winner_abbr,
    g.overtimes,
    g.is_neutral
from {{ ref('stg_games') }} g
join {{ ref('dim_teams') }} h on h.team_id = g.home_team_id
join {{ ref('dim_teams') }} a on a.team_id = g.away_team_id
