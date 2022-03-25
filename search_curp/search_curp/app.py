from .db import get_db

import json
import hashlib
import requests
import html_to_json

database = get_db()

headers_cors = {
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "*"
}


def get_user(username):
    user = database.get("""
       select *from usuarios_gestion
        where username=%s""", username)
    return user


def authenticate(username, password):
    """Returns a user dict on success and an error string otherwise."""
    if not username:
        return 'Se requiere autenticacion'
    user = get_user(username)
    if not user:
        return 'Usuario "%s" no existe.' % username
    elif user.status is False:
        return 'Usuario inactivo'
    elif hashlib.md5(user.salt.encode('utf-8') + password.encode('utf-8')).hexdigest() == user.salted_password_md5:
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
            'headers':headers_cors,
            'statusCode': 401,
            'body': json.dumps({
                'message': 'Autenticacion Basica requerida.'})
        }
    if not 'Basic' in headers.Authorization:
        return {
            'headers': headers_cors,
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
        from .utils import validate_body
        p = validate_body(expected,body)
        if isinstance(p,dict):
            url = "https://us-west4-arsus-production.cloudfunctions.net/curp"

            params = {
                'curp':p.curp,
                'apiKey':'YcB9uq74BKhMK6kpES2EbhaPziw2'
            }
            response = requests.request("GET", url, params=params)
            r = response.json()
            try:
                return {
                    'headers': headers_cors,
                    'statusCode': 200,
                    'body': json.dumps({
                        'nombre': r['name'],
                        'apellid_pat': r['fatherName'],
                        'apellido_mat': r['motherName'],
                        'fecha_nac': r['birthday'].split('T')[0],
                        'sexo': p.curp[10]
                    })
                }
            except Exception:
                return {
                    'headers': headers_cors,
                    'statusCode': 400,
                    'body': json.dumps({'message': 'No fue posible obtener los datos de tu CURP'})
                }
        else:
            return {
                'headers': headers_cors,
                'statusCode': 400,
                'body': json.dumps({'message': p})
            }
    return {
        'headers': headers_cors,
        'statusCode': 400,
        'body': json.dumps({'message': user_or_error})
    }



