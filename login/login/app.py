import json
import hashlib
from .db import get_db

database = get_db()

def get_user(username):
    user = database.get("""
       select *from 
        where username=%s""", username)
    return user

def authenticate(username, password):
    """Returns a user dict on success and an error string otherwise."""
    if not username:
        return 'Authentication required.'
    user = get_user(username)
    if not user:
        return 'User "%s" does not exist.' % username
    elif not user.status :
        return 'Account disabled.'
    elif hashlib.md5(user.salt.encode('utf-8') + password.encode('utf-8')).hexdigest() == user.salted_password_md5:
        #now = ms()
        # only update last_login_ms every 5 minutes
        database.execute('update user set last_login_hour=%s, last_login_date where id=%s', '00:00:00','2022-02-01', user.id)
        return user

    else:
        return 'Incorrect password.'

def lambda_handler(event, context):
    """function to make a simple login to app
    """
    from .db import Row
    b = json.loads(event['body'])
    keys = [k for k in b.keys()]
    #body = [Row(dict(k,r[k])) for k,r in zip(keys,b)]
    return {
        'statusCode': 200,
        'body': json.dumps(
        {
            'info': b
        })
    }
    user_or_error = security_scheme.authenticate(p.username, p.password, request.remote_addr, p.pin)

    if isinstance(user_or_error, dict):
        user_auth_plugin.session_login(user_or_error.id)
        return project(user_or_error, ('username', 'name', 'currency', 'role'))

    raise HTTPError(400, user_or_error)




    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "message": info,
                # "location": ip.text.replace("\n", "")
            }
        ),
    }