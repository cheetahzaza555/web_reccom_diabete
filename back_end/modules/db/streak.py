"""One streak calculation for the dashboard and exercise completion."""
from datetime import date, datetime, timedelta, timezone

from SPARQLWrapper import SPARQLWrapper, JSON, POST
from modules.config import GRAPHDB_READ, GRAPHDB_WRITE
from .connection import validate_id


def today_in_thailand():
    return datetime.now(timezone(timedelta(hours=7))).date()


def calculate_streak(rows, today=None, old_max=0):
    today = today or today_in_thailand()
    days = {}
    for row in rows:
        day = date.fromisoformat(row['planDate']['value'][:10])
        if day <= today:
            days.setdefault(day, set()).add(row.get('planStatus', {}).get('value', 'Pending'))
    current = maximum = 0
    previous = None
    last = ''
    for day, statuses in sorted(days.items()):
        if previous is not None and day != previous + timedelta(days=1):
            current = 0
        if 'Completed' in statuses:
            current += 1
            last = day.isoformat()
        elif statuses <= {'Rest', 'RestDay', 'OffDay'}:
            pass
        elif day == today and statuses == {'Pending'}:
            pass  # Today's scheduled session is not overdue yet.
        else:
            current = 0
        maximum = max(maximum, current)
        previous = day
    # Do not expire yesterday's streak before today has ended.
    if previous is None or previous < today - timedelta(days=1):
        current = 0
    return {'current_streak': current, 'max_streak': max(old_max, maximum), 'last_date': last}


def _read(query):
    client = SPARQLWrapper(GRAPHDB_READ)
    client.setTimeout(20)
    client.setReturnFormat(JSON)
    client.setQuery('PREFIX ex: <http://example.org/diabetes#> ' + query)
    return client.query().convert()['results']['bindings']


def _patient(patient_id):
    if not validate_id(patient_id):
        raise ValueError('Invalid patient ID')
    return 'Patient' + str(patient_id).replace('Patient', '').replace('SUPA', '')


def get_patient_streak(patient_id):
    pid = _patient(patient_id)
    # Fail instead of replacing an unreadable history with a made-up streak.
    rows = _read(f'''SELECT DISTINCT ?planDate ?planStatus WHERE {{
        ex:{pid} ex:hasMonthlyPlan/ex:hasWeeklyPlan/ex:hasDailyPlan ?day .
        ?day ex:planDate ?planDate .
        OPTIONAL {{ ?day ex:planStatus ?planStatus }}
    }}''')
    records = _read(f'SELECT ?max WHERE {{ ex:{pid} ex:maxStreak ?max }}')
    old_max = max((int(row['max']['value']) for row in records), default=0)
    return calculate_streak(rows, old_max=old_max)


def process_patient_streak_on_complete(patient_id):
    result = get_patient_streak(patient_id)
    pid = _patient(patient_id)
    last = (f'ex:{pid} ex:lastExerciseDate "{result["last_date"]}"^^xsd:date .'
            if result['last_date'] else '')
    client = SPARQLWrapper(GRAPHDB_WRITE)
    client.setTimeout(20)
    client.setMethod(POST)
    client.setQuery(f'''PREFIX ex: <http://example.org/diabetes#>
        PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
        DELETE {{ ex:{pid} ex:currentStreak ?c ; ex:maxStreak ?m ; ex:lastExerciseDate ?d . }}
        INSERT {{ ex:{pid} ex:currentStreak {result['current_streak']} ; ex:maxStreak ?newMax . {last} }}
        WHERE {{
            OPTIONAL {{ ex:{pid} ex:currentStreak ?c }}
            OPTIONAL {{ ex:{pid} ex:maxStreak ?m }}
            OPTIONAL {{ ex:{pid} ex:lastExerciseDate ?d }}
            BIND(IF(COALESCE(?m, 0) > {result['max_streak']}, ?m, {result['max_streak']}) AS ?newMax)
        }}''')
    client.query()
    return result
