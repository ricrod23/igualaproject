from .db import get_db

import json
import hashlib
import datetime
import random
import requests
import html_to_json


database = get_db()


def random_text(n=None):
    import os
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


def lambda_handler(event, context):
    """function to make a simple save licencia to app
    """
    import base64
    from .db import Row
    headers = Row(dict(event['headers']))
    if not 'Authorization' in headers:
        return {
            'statusCode': 401,
            'body': json.dumps({
                'message': 'Autenticacion Basica requerida.'})
        }
    if not 'Basic' in headers.Authorization:
        return {
            'statusCode': 401,
            'body': json.dumps({
                'message': 'Autenticacion Basica requerida.'})
        }
    auth = headers.Authorization.replace('Basic ','')
    decoded = base64.b64decode(auth).decode('utf-8')
    user_password = decoded.split(':')
    user_or_error = authenticate(user_password[0],user_password[1])
    if isinstance(user_or_error,dict):
        b = event['queryStringParameters']
        body = Row(b)
        expected = (('curp',str),)
        #falta insert a contacto en caso de emergencia
        from .utils import validate_body
        p = validate_body(expected,body)
        if isinstance(p,dict):
            url = "http://www.renapo.sep.gob.mx/wsrenapo/MainControllerParam"

            payload = 'curp=%s&Submit=Enviar' % p.curp.lower()
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            response = requests.request("POST", url, headers=headers, data=payload)
            try:
                json_ = html_to_json.convert(response.text)
                apellid_pat = json_['html'][0]['body'][0]['table'][0]['tr'][2]['td'][1]['div'][0]['_value']
                apellido_mat = json_['html'][0]['body'][0]['table'][0]['tr'][3]['td'][1]['div'][0]['_value']
                nombre = json_['html'][0]['body'][0]['table'][0]['tr'][15]['td'][1]['div'][0]['_value']
                fecha_nac = json_['html'][0]['body'][0]['table'][0]['tr'][10]['td'][1]['div'][0]['_value']
                sexo= json_['html'][0]['body'][0]['table'][0]['tr'][19]['td'][1]['div'][0]['_value']
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'nombre': nombre,
                        'apellid_pat': apellid_pat,
                        'apellido_mat': apellido_mat,
                        'fecha_nac': fecha_nac,
                        'sexo': sexo
                    })
                }
            except Exception:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'message': 'No fue posible obtener los datos de tu CURP'})
                }



        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'message': p})
            }
    return {
        'statusCode': 400,
        'body': json.dumps({'message': user_or_error})
    }



