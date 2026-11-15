select team_id, abbreviation as team_abbr, name as team_name
from {{ source('nba', 'teams') }}
