from .db import get_db

import json
import hashlib
import datetime
import random
from pytz import timezone
import qrcode
import requests
import boto3
from io import BytesIO
from PIL import Image

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

def set_llave(id, curp):
    salt = random_text(32)
    salted_key_md5 = hashlib.md5(salt.encode('utf-8') + curp.encode('utf-8')).hexdigest()
    database.execute('update contribuyentes_licencias set llave_licencia_md5=%s, llave_licencia=%s where id_contribuyente=%s', salt, salted_key_md5, id)
    return salted_key_md5


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
    auth = headers.Authorization.replace('Basic ','')
    decoded = base64.b64decode(auth).decode('utf-8')
    user_password = decoded.split(':')
    user_or_error = authenticate(user_password[0],user_password[1])
    if isinstance(user_or_error,dict):
        b = json.loads(event['body'])
        body = Row(dict(b))
        expected = (('id_permiso',int),
                    ('curp', str),
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
        p = validate_body(expected,body)
        if isinstance(p,dict):
            exists = database.get('select id_permiso, status_permiso from permisos_comerciales_descrip where id_permiso =%s', p.id_permiso)
            if not exists:
                return {
                    'headers': headers_cors,
                    'statusCode': 400,
                    'body': json.dumps({'message': 'Permiso no encontrado'})
                }
            if exists.status_permiso:
                return {
                    'headers': headers_cors,
                    'statusCode': 400,
                    'body': json.dumps({'message': 'No es posible editar un permiso ya activado'})
                }
            now_date = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
            now_hour = datetime.datetime.now(tz=timezone('America/Mexico_City')).time()
            if p.status_permiso or p.status_pago:
                if not p.status_pago or not p.status_permiso:
                    return {
                        'headers': headers_cors,
                        'statusCode': 400,
                        'body': json.dumps({'message': 'Error con estatus de pago o estatus de permiso'})
                    }
                if p.folio_pago == '':
                    return {
                        'headers': headers_cors,
                        'statusCode': 400,
                        'body': json.dumps({'message': 'Folio de pago no puede ir vacio'})
                    }
            if p.status_pago:
                from dateutil.relativedelta import relativedelta
                final_date = now_date + relativedelta(years=5)
                database.update('permisos_comerciales_descrip', 'id_permiso', p.id_permiso,
                                razon_social=p.razon_social.upper(),
                                denominacion=p.denominacion.upper(),
                                comercio_calle_numero=p.comercio_calle_numero,
                                comercio_colonia=p.comercio_colonia,
                                comercio_cp=p.comercio_cp,
                                giro=p.giro,
                                tipo=p.tipo,
                                horario_inicio=p.horario_inicio,
                                horario_cierre=p.horario_cierre,
                                ultima_actualizacion_fecha=now_date,
                                ultima_actualizacion_hora=now_hour,
                                id_ultima_modificacion=user_or_error.id,
                                status_permiso=True,
                                status_pago=True,
                                folio_pago=p.folio_pago,
                                vigencia_inicio=now_date,
                                vigencia_fin=final_date
                )
            else:
                database.update('permisos_comerciales_descrip', 'id_permiso', p.id_permiso,
                                razon_social=p.razon_social.upper(),
                                denominacion=p.denominacion.upper(),
                                comercio_calle_numero=p.comercio_calle_numero,
                                comercio_colonia=p.comercio_colonia,
                                comercio_cp=p.comercio_cp,
                                giro=p.giro,
                                tipo=p.tipo,
                                horario_inicio=p.horario_inicio,
                                horario_cierre=p.horario_cierre,
                                ultima_actualizacion_fecha=now_date,
                                ultima_actualizacion_hora=now_hour,
                                id_ultima_modificacion=user_or_error.id
                                )
            database.update('contribuyentes_permisos_comerciales','id_permiso', p.id_permiso,
                            curp=p.curp,
                            rfc=p.rfc,
                            propietario_nombre=p.propietario_nombre,
                            propietario_apellidos=p.propietario_apellidos,
                            propietario_colonia=p.propietario_colonia,
                            propietarion_calle_numero=p.propietario_callle_numero,
                            propietario_cp=p.propietario_cp,
                            telefono_celular=p.telefono_celular,
                            telefono_fijo=p.telefono_fijo,
                            email=p.email,
                            fecha_nacimiento=p.fecha_nacimiento,
                            sexo=p.sexo,
                            ultima_actualizacion_fecha=now_date,
                            ultima_actualizacion_hora=now_hour,
                            id_ultima_modificacion=user_or_error.id
                        )
            return {
                'headers': headers_cors,
                'statusCode': 200,
                'body': json.dumps({'message': 'Guardado con Exito'})
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



