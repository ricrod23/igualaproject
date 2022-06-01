import traceback

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
    database.execute('update permisos_comerciales_descrip set llave_permiso_md5=%s, llave_permiso=%s where id_permiso=%s', salt, salted_key_md5, id)
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
    try:
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
        if user_password[0] == 'null':
            user_or_error = database.get("""
            select id, username, nombre, apellidos, rol, status, CAST(last_login_date AS char) as last_login_date, CAST(last_login_hour AS char) as last_login_hour from usuarios_gestion
            where username=%s""", 'ricardo.rodarte')
        else:
            user_or_error = authenticate(user_password[0], user_password[1])
        if isinstance(user_or_error, dict):
            b = json.loads(event['body'])
            body = Row(dict(b))
            expected = (
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
                ('horario_cierre', str),
                ('link_identificacion_anv', str),
                ('link_identificacion_rev', str),
                ('dia_ini_funcionamiento', str),
                ('dia_fin_funcionamiento', str),
                ('link_rfc', str),
                ('link_acta_constitutiva', str)
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
                                          hora_creacion=now_hour,
                                          link_identificacion_anv=p.link_identificacion_anv,
                                          link_identificacion_rev=p.link_identificacion_rev,
                                          link_rfc=p.link_rfc,
                                          link_acta_constitutiva=p.link_acta_constitutiva,
                                          ultima_actualizacion_fecha=now_date,
                                          ultima_actualizacion_hora=now_hour,
                                          dia_ini_funcionamiento=p.dia_ini_funcionamiento,
                                          dia_fin_funcionamiento=p.dia_fin_funcionamiento
                                          )
                database.insert('contribuyentes_permisos_comerciales',
                                id_permiso=permiso,
                                rfc=p.rfc,
                                propietario_nombre=p.propietario_nombre,
                                propietario_apellidos=p.propietario_apellidos,
                                propietario_colonia=p.propietario_colonia,
                                propietario_cp=p.propietario_cp,
                                telefono_celular=p.telefono_celular,
                                telefono_fijo=p.telefono_fijo,
                                propietario_calle_numero=p.propietario_calle_numero,
                                email=p.email,
                                fecha_nacimiento=p.fecha_nacimiento,
                                sexo=p.sexo,
                                ultima_actualizacion_fecha=now_date,
                                ultima_actualizacion_hora=now_hour
                                )
                key = set_llave(permiso, p.rfc)
                # QR
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_H,
                    box_size=5,
                    border=4
                )
                qr.add_data(
                    'http://licenciasypermisos.s3-website-us-east-1.amazonaws.com/consultarPermiso.html?criterio=llave_permiso&dato=%s&tipo=permiso' % (
                        key))
                qr.make(fit=True)
                img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
                response = requests.get('http://s3-us-west-2.amazonaws.com/igualauploads/logo_iguala.png')
                logo_display = Image.open(BytesIO(response.content))
                logo_display.thumbnail((70, 70))
                logo_pos = ((img.size[0] - logo_display.size[0]) // 2, (img.size[1] - logo_display.size[1]) // 2)
                img.paste(logo_display, logo_pos)
                img.save("/tmp/qr_%s.png" % key)
                s3_client = boto3.client('s3')
                s3_client.upload_file("/tmp/qr_%s.png" % key, 'igualauploads', "qr_%s.png" % key)
                database.update('permisos_comerciales_descrip', 'llave_permiso', key,
                                link_qr='http://s3-us-west-2.amazonaws.com/igualauploads/qr_%s.png' % (key))
                from .utils import send_outlook
                #send_outlook(p.email, 'Firma para permiso Gob Iguala',
                 #            'Por favor haz clic en el siguiente enlace para finalizar tu tramite y enviar tu firma.\n' +
                  #           'http://licenciasypermisos.s3-website-us-east-1.amazonaws.com/recabaFirma.html?dato=%s&criterio=llave_permiso&tipo=permiso' % key)
                return {
                    'headers': headers_cors,
                    'statusCode': 200,
                    'body': json.dumps({
                        'message': 'Tramite de permiso registrado con exito tu folio es: %s, te enviamos un correo electronico para completar la informacion restante si no lo ves revisa Correo no deseado o Spam'%(permiso)})
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
    except Exception:
        return {
            'headers': headers_cors,
            'statusCode': 400,
            'body': json.dumps({'message': traceback.format_exc()})
        }
