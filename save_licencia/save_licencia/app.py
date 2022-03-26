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
                    ('sexo', str),
                    ('link_foto', str),
                    ('link_identificacion_anv', str),
                    ('link_identificacion_rev', str),
                    ('link_certificado_tipo_sangre', str)
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
                            telefono_fijo=p.telefono_fijo,
                            email = p.email,
                            tipo_sangre = p.tipo_sangre,
                            alergias = p.alergias,
                            donante = p.donante,
                            llave_licencia = 'lallave',
                            fecha_creacion = now_date,
                            id_usuario_creo = user_or_error.id,
                            hora_creacion = now_hour,
                            alergias_descripcion =p.alergias_descripcion,
                            tipo_licencia=p.tipo_licencia,
                            fecha_nacimiento=datetime.datetime.strptime(p.fecha_nacimiento,'%Y-%m-%d').date(),
                            sexo=p.sexo.upper(),
                            link_foto=p.link_foto,
                            link_identificacion_anv= p.link_identificacion_anv,
                            link_identificacion_rev=p.link_identificacion_rev,
                            ultima_actualizacion_fecha=now_date,
                            ultima_actualizacion_hora=now_hour,
                            link_certificado_tipo_sangre=p.link_certificado_tipo_sangre
                        )
            id = database.get('select id_contribuyente from contribuyentes_licencias where curp = %s',p.curp.upper()).id_contribuyente
            database.insert('contactos_emergencia',
                            id_contribuyente= id,
                            nombre = p.nombre_emergencia,
                            apellidos = p.apellidos_emergencia,
                            telefono_contacto = p.telefono_emergencia
                        )
            key = set_llave(id, p.curp)
            #QR
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=5,
                border=4
            )
            qr.add_data(
                'http://licenciasypermisos.s3-website-us-east-1.amazonaws.com/consultarLicencia.html?criterio=llave_licencia&dato=%s&tipo=licenica' % (
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
            database.update('contribuyentes_licencias','id_contribuyente',id,link_qr='http://s3-us-west-2.amazonaws.com/igualauploads/qr_%s.png'%(key))

            from .utils import send_outlook
            send_outlook(p.email,'Firma para licencia Gob Iguala', 'Por favor haz clic en el siguiente enlace para finalizar tu tramite y enviar tu firma.\n'+
                                                                   'http://licenciasypermisos.s3-website-us-east-1.amazonaws.com/recabaFirma.html?dato=%s&criterio=llave_licencia&tipo=licencia'%key)
            return {
                'headers': headers_cors,
                'statusCode': 200,
                'body': json.dumps({'message': 'Tramite de licencia registrado con exito tu Folio de seguimiento es: %s, te enviamos un correo electronico para completar la informacion restante si no lo ves revisa Correo no deseado o Spam'%id})
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



