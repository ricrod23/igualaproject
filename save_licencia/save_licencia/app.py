from .db import get_db

import json
import hashlib
import datetime
import random
from pytz import timezone


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
        b = json.loads(event['body'])
        body = Row(dict(b))
        expected = (('curp',str),
                    ('nombre', str),
                    ('apellidos',str),
                    ('calle_numero', str),
                    ('colonia',str),
                    ('municipio',str),
                    ('estado',str),
                    ('cp',str),
                    ('telefono_celular',str),#validar que sea numero y celular
                    ('telefono_fijo', str),#validar que sea numero fijo
                    ('email', str),#validar que si sea correo
                    ('tipo_sangre', str),
                    ('alergias', bool),
                    ('donante', bool),
                    ('alergias_descripcion',str),
                    ('tipo_licencia', str),
                    ('nombre_emergencia',str),
                    ('apellidos_emergencia', str),
                    ('telefono_emergencia', str),
                    ('fecha_nacimiento', str),
                    ('sexo', str)
                )
        from .utils import validate_body
        p = validate_body(expected,body)
        if isinstance(p,dict):
            exists = database.get('select curp from contribuyentes_licencias where curp =%s', p.curp.upper())
            if exists:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'message': 'CURP ya fue registrada'})
                }
            now_date = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
            now_hour = datetime.datetime.now(tz=timezone('America/Mexico_City')).time()
            database.insert('contribuyentes_licencias',
                            curp= p.curp.upper(),
                            nombre= p.nombre,
                            apellidos= p.apellidos,
                            calle_numero= p.calle_numero,
                            colonia= p.colonia,
                            municipio= p.municipio,
                            estado= p.estado,
                            cp= p.cp,
                            telefono_celular= p.telefono_celular,
                            email = p.email,
                            tipo_sangre = p.tipo_sangre,
                            alergias = p.alergias,
                            donante = p.donante,
                            llave_licencia = 'lallave',
                            fecha_creacion = now_date,
                            id_usuario_creo = user_or_error.id,
                            hora_creacion = now_hour,
                            alergias_descripcion = p.alergias_descripcion,
                            tipo_licencia= p.tipo_licencia,
                            fecha_nacimiento= datetime.datetime.strptime(p.fecha_nacimiento,'%d/%m/%Y').date(),
                            sexo= p.sexo.upper()
                        )
            id = database.get('select id_contribuyente from contribuyentes_licencias where curp = %s',p.curp.upper()).id_contribuyente
            database.insert('contactos_emergencia',
                            id_contribuyente= id,
                            nombre = p.nombre_emergencia,
                            apellidos = p.apellidos_emergencia,
                            telefono_contacto = p.telefono_emergencia
                        )
            #enviar email para la firma y foto
            return {
                'statusCode': 200,
                'body': json.dumps({'message': 'Tramite de licencia registrado con exito, te enviamos un correo electronico para completar la informacion restante'})
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



