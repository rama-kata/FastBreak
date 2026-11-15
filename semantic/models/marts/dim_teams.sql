select team_id, team_abbr, team_name
from {{ ref('stg_teams') }}
