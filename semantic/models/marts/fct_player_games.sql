-- One row per player per game they played in, with the definitions FastBreak's
-- answers depend on worked out once.
with stats as (
    select
        *,
        (pts >= 10)::int + (reb >= 10)::int + (ast >= 10)::int
            + (stl >= 10)::int + (blk >= 10)::int as double_digit_categories
    from {{ ref('stg_player_game_stats') }}
)
select
    s.game_id,
    tg.game_date,
    tg.season,
    tg.season_type,
    s.player_id,
    p.player_name,
    s.team_id,
    tg.team_abbr,
    tg.opponent_id,
    tg.opponent_abbr,
    tg.home_away,
    tg.is_neutral,
    tg.won as team_won,
    s.is_starter,
    not s.is_starter as off_bench,
    s.seconds,
    s.minutes,
    s.fgm, s.fga, s.fg3m, s.fg3a, s.ftm, s.fta,
    s.oreb, s.dreb, s.reb, s.ast, s.stl, s.blk, s.tov, s.pf, s.pts,
    s.plus_minus,
    s.double_digit_categories,
    s.double_digit_categories >= 2 as is_double_double,
    s.double_digit_categories >= 3 as is_triple_double
from stats s
join {{ ref('fct_team_games') }} tg on tg.game_id = s.game_id and tg.team_id = s.team_id
join {{ ref('dim_players') }} p on p.player_id = s.player_id
