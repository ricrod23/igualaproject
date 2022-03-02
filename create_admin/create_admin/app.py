import json
import hashlib
from .db import get_db
import datetime

database = get_db()

def get_user(username):
    user = database.get("""
       select *from usuarios_gestion
        where username=%s""", username)
    return user

def authenticate(username, password):
    from pytz import timezone
    """Returns a user dict on success and an error string otherwise."""
    if not username:
        return 'Authentication required.'
    user = get_user(username)
    if not user:
        return 'User "%s" does not exist.' % username
    elif user.status is False:
        return 'Account disabled.'
    elif hashlib.md5(user.salt.encode('utf-8') + password.encode('utf-8')).hexdigest() == user.salted_password_md5:
        now_date = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
        now_hour = datetime.datetime.now(tz=timezone('America/Mexico_City')).time()
        database.execute('update usuarios_gestion set last_login_hour=%s, last_login_date=%s where id=%s', now_hour,
                         now_date, user.id)
        user_upd = database.get("""
        select id, username, nombre, apellidos, rol, status, CAST(last_login_date AS char) as last_login_date, CAST(last_login_hour AS char) as last_login_hour from usuarios_gestion
        where username=%s""", username)
        return user_upd
    else:
        return 'Incorrect password.'

def lambda_handler(event, context):
    """function to make a simple login to app
    """
    return {
        'status_code':200,
        'body':json.dumps(event)
    }
    from .db import Row
    b = json.loads(event['body'])
    body = Row(dict(b))
