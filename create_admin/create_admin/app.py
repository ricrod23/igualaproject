import json
import hashlib
from .db import get_db
import datetime
import random


database = get_db()

def random_text(n=None):
    import random, os
    from base64 import b64encode
    if n is None:
        n = random.randint(0, 128)
    return b64encode(os.urandom(n)).decode('utf-8')[:n]


def get_user(username):
    user = database.get("""
       select *from usuarios_gestion
        where username=%s""", username)
    return user

def authenticate(username, password):
    from pytz import timezone
    """Returns a user dict on success and an error string otherwise."""
    if not username:
        return 'Se requiere autenticacion'
    user = get_user(username)
    if not user:
        return 'Usuario "%s" no existe.' % username
    elif user.status is False:
        return 'Usuario inactivo'
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

def check_password(password):
    import re
    """Return None on success and an error string otherwise."""
    if len(password) < 8:
        return 'password must be 8 or more characters'
    if not re.search(r'\d', password):
        return 'password must contain at least 1 digit'
    if not re.search(r'[a-zA-Z]', password):
        return 'password must contain at least 1 alphabetic character'

def generate_password():
    length = 10
    chars = '23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    while True:
        password = ''.join([random.choice(chars) for x in range(length)])
        if not check_password(password):
            return password

def update_password(id, password):
    salt = random_text(32)
    salted_password_md5 = hashlib.md5(salt.encode('utf-8') + password.encode('utf-8')).hexdigest()
    database.execute('update usuarios_gestion set salt=%s, salted_password_md5=%s where id=%s', salt, salted_password_md5, id)

def lambda_handler(event, context):
    """function to make a simple login to app
    """
    import base64
    from .db import Row
    headers = Row(dict(event['headers']))
    auth = headers.Authorization.replace('Basic ','')
    decoded = base64.b64decode(auth).decode('utf-8')
    user_password = decoded.split(':')
    user_or_error = authenticate(user_password[0],user_password[1])
    if isinstance(user_or_error,dict):
        b = json.loads(event['body'])
        body = Row(dict(b))
        if 'username' in body and 'nombre' in body and 'apellido' in body and 'rol' in body:
            from pytz import timezone
            now_date = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
            now_hour = datetime.datetime.now(tz=timezone('America/Mexico_City')).time()
            new_password = generate_password()
            user = database.get('select id, username from usuarios_gestion where username = %s', body.username)
            if not user:
                database.execute('''insert into usuarios_gestion (username,nombre,apellidos,rol,status,creado_por_username,
                fecha_creacion, hora_creacion) values (%s,%s,%s,%s,%s,%s,%s,%s)''',body.username, body.nombre, body.apellido,
                                 body.rol, True, user_password[0],now_date,now_hour)
                user = database.get('select id, username from usuarios_gestion where username = %s', body.username)
                update_password(user.id,new_password)
                user['password'] = new_password
                return {
                    'statusCode': 200,
                    'body': json.dumps(user)
                }
            else:
                user_or_error = 'Usuario ya existe.'
        else:
            user_or_error = 'Faltan campos para crear usuario'

    return {
        'statusCode': 401,
        'body': json.dumps({
            'message': user_or_error})
    }



