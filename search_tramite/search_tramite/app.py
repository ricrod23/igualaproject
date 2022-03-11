from .db import get_db

import json
import hashlib
import datetime

headers_cors = {
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "*"
}

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
            'headers': headers_cors,
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
        #falta insert a contacto en caso de emergencia
        from .utils import validate_body
        p = validate_body(expected,body)
        if isinstance(p,dict):
            info = database.get('''select * from contribuyentes_licencias cl inner join 
            contactos_emergencia ce on cl.id_contribuyente = ce.id_contribuyente where cl.curp=%s ''',p.curp.lower())
            info['fecha_creacion'] = str(info.fecha_creacion)
            info['hora_creacion'] = str(info.hora_creacion)[:8]
            info['fecha_nacimiento'] = str(info.fecha_nacimiento)
            if info['vigencia_inicio'] is not None:
                info['vigencia_inicio'] = str(info.vigencia_inicio)
            if info['vigencia_fin'] is not None:
                info['vigencia_fin'] = str(info.vigencia_fin)
            if info:
                return {
                    'headers': headers_cors,
                    'statusCode': 200,
                    'body': json.dumps(info)
                }
            else:
                return {
                    'headers': headers_cors,
                    'statusCode': 400,
                    'body': json.dumps({'message': 'No existe informacion con la CURP proporcionada'})
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



