from .db import get_db

import json
import hashlib
import datetime
import random
from pytz import timezone

headers_cors = {
    "Access-Control-Allow-Headers": "*",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "*"
}

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
    auth = headers.Authorization.replace('Basic ', '')
    decoded = base64.b64decode(auth).decode('utf-8')
    user_password = decoded.split(':')
    user_or_error = authenticate(user_password[0], user_password[1])
    if isinstance(user_or_error, dict):
        b = json.loads(event['body'])
        body = Row(dict(b))
        expected = (('curp', str),
                    ('rfc', str),
                    ('propietario_nombre', str),
                    ('propietario_apellidos', str),
                    ('propietario_calle_numero', str),
                    ('propietario_colonia', str),
                    ('propietario_cp', str),
                    ('telefono_celular', str),  # validar que sea numero y celular
                    ('telefono_fijo', str),  # validar que sea numero fijo
                    ('email', str),  # validar que si sea correo
                    ('fecha_nacimiento', str),
                    ('sexo', str),
                    ('razon_social', str),
                    ('denominacion', str),
                    ('comercio_calle_numero', str),
                    ('comercio_colonia', str),
                    ('comercio_cp', str),
                    ('giro', str),
                    ('tipo', str),
                    ('horario_inicio', str),
                    ('horario_cierre', str)
                    )
        from .utils import validate_body
        p = validate_body(expected, body)
        if isinstance(p, dict):
            now_date = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
            now_hour = datetime.datetime.now(tz=timezone('America/Mexico_City')).time()
            permiso = database.insert('permisos_comerciales_descrip',
                                      razon_social=p.razon_social.upper(),
                                      denominacion=p.denominacion.upper(),
                                      comercio_calle_numero=p.comercio_calle_numero,
                                      comercio_colonia=p.comercio_colonia,
                                      comercio_cp=p.comercio_cp,
                                      giro=p.giro,
                                      tipo=p.tipo,
                                      horario_inicio=p.horario_inicio,
                                      horario_cierre=p.horario_cierre,
                                      status_permiso=False,
                                      llave_permiso='lallave',
                                      fecha_creacion=now_date,
                                      id_usuario_creo=user_or_error.id,
                                      hora_creacion=now_hour

                                      )
            database.insert('contribuyentes_permisos_comerciales',
                            id_permiso=permiso,
                            curp=p.curp,
                            rfc=p.rfc,
                            propietario_nombre=p.propietario_nombre,
                            propietario_apellidos=p.propietario_apellidos,
                            propietario_colonia=p.propietario_colonia,
                            propietario_cp=p.propietario_cp,
                            telefono_celular=p.telefono_celular,
                            telefono_fijo=p.telefono_fijo,
                            email=p.email,
                            fecha_nacimiento=p.fecha_nacimiento,
                            sexo=p.sexo
                            )
            from .utils import send_outlook
            send_outlook(p.email, 'Firma para permiso Gob Iguala',
                         'Por favor haz clic en el siguiente enlace para finalizar tu tramite y enviar tu firma.\n' +
                         'http://licenciasypermisos.s3-website-us-east-1.amazonaws.com/recabaFirma.html')
            return {
                'headers': headers_cors,
                'statusCode': 200,
                'body': json.dumps({
                                       'message': 'Tramite de permiso registrado con exito, te enviamos un correo electronico para completar la informacion restante si no lo ves revisa Correo no deseado o Spam'})
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
