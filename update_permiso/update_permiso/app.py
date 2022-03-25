from .db import get_db

import json
import hashlib
import datetime
import random
from pytz import timezone
import boto3

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

months = {
    '01': 'ENERO',
    '02': 'FEBRERO',
    '03': 'MARZO',
    '04': 'ABRIL',
    '05': 'MAYO',
    '06': 'JUNIO',
    '07': 'JULIO',
    '08': 'AGOSTO',
    '09': 'SEPTIEMBRE',
    '10': 'OCTUBRE',
    '11': 'NOVIEMBRE',
    '12': 'DICIEMBRE'
}

def create_pdf(p):
    import os
    import math
    import io

    import pytz
    from PyPDF2 import PdfFileReader, PdfFileWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    
    
    information = database.get('''select propietario_calle_numero, propietario_colonia, propietario_cp, propietario_nombre, propietario_apellidos,
    razon_social, denominacion, comercio_calle_numero, comercio_colonia, comercio_cp, giro, tipo, horario_inicio, horario_cierre, dia_ini_funcionamiento,
     dia_fin_funcionamiento, link_qr, llave_permiso from permisos_comerciales_descrip pd inner join contribuyentes_permisos_comerciales cp
     on pd.id_permiso= cp.id_permiso where pd.id_permiso = %s''', p.id_permiso)

    now = datetime.datetime.now(pytz.timezone('America/Mexico_City')).date()

    fecha_emision = 'IGUALA, GRO. A %s DE %s DEL %s' % (
    now.strftime('%d'), months.get(now.strftime('%m'), ''), now.strftime('%Y'))
    domicilio_contribuyente = 'DOMICILIO PARTICULAR: %s, %s, IGUALA, GRO, %s' % (
    information.propietario_calle_numero, information.propietario_colonia, \
    information.propietario_cp)
    domicilio_establecimiento = 'DOMICILIO DEL ESTABLECIMIENTO: %s, %s, %s' % (
    information.comercio_calle_numero, information.comercio_colonia, \
    information.comercio_cp)
    horario_funcionamiento = 'HORARIO DE FUNCIONAMIENTO: %s a %s DE %s a %s HRS.' % (information.dia_ini_funcionamiento, \
                                                                                     information.dia_fin_funcionamiento, \
                                                                                     information.horario_inicio,
                                                                                     information.horario_cierre)
    tipo = 'TIPO: %s' % information.tipo
    giro = 'GIRO O ACTIVIDAD: %s' % information.giro
    razon_social = 'RAZON SOCIAL Y/O DENOMINACION: %s / %s' % (information.razon_social, information.denominacion)
    propietario = 'PROPIETARIO: %s %s' % (information.propietario_nombre, information.propietario_apellidos)
    dictionary = {
        'fecha_emision': fecha_emision,
        'domicilio_contribuyente': domicilio_contribuyente,
        'domicilio_comercio': domicilio_establecimiento,
        'horario': horario_funcionamiento,
        'tipo': tipo,
        'giro': giro,
        'razon_social': razon_social,
        'propietario': propietario,
    }

    # get image
    s3 = boto3.client(
        aws_access_key_id='AKIAUAAEXHS5LFZSLGZC',
        aws_secret_access_key='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',
        region_name='us-west-2',
        service_name='s3'
    )

    qr_file_name = 'qr_' + information.llave_permiso + '.png'
    plantilla_file_name = 'iguala_plantilla_permiso2.pdf'

    with open('/tmp/' + qr_file_name, 'wb') as data:
        s3.download_fileobj('igualauploads', qr_file_name, data)
    with open('/tmp/' + plantilla_file_name, 'wb') as data:
        s3.download_fileobj('igualauploads', plantilla_file_name, data)

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.drawString(520, 715, "N° %s"%(str(p.id_permiso)))
    can.setFont('Courier', 11)
    lines = []
    for i, r in enumerate(dictionary.keys()):
        pre_lines = []
        if (len(dictionary[r])) > 69:
            num_of_lines = int(math.ceil(len(dictionary[r]) / 69))
            for j in range(0, num_of_lines):
                pre_lines.append(dictionary[r][j * 70:(j + 1) * 70])
        else:
            lines.append(dictionary[r])

        if (len(pre_lines) > 1):
            for j in range(len(pre_lines), 0, -1):
                lines.append(pre_lines[j - 1])
    for i, r in enumerate(lines):
        can.drawString(32, (i + 21) * 22, r)
    can.drawImage('/tmp/qr_' + information.llave_permiso + '.png', 495, 615, 85, 85)
    can.save()

    # move to the beginning of the StringIO buffer
    packet.seek(0)

    # create a new PDF with Reportlab
    new_pdf = PdfFileReader(packet)
    # read your existing PDF
    read_plantilla = open("/tmp/iguala_plantilla_permiso2.pdf", "rb")
    existing_pdf = PdfFileReader(read_plantilla)
    output = PdfFileWriter()
    # add the "watermark" (which is the new pdf) on the existing page
    page = existing_pdf.getPage(0)
    page.mergePage(new_pdf.getPage(0))
    output.addPage(page)
    # finally, write "output" to a real file
    outputStream = open("/tmp/permiso_%s.pdf" % (information.llave_permiso), "wb")
    output.write(outputStream)
    outputStream.close()
    read_plantilla.close()

    try:
        os.remove('/tmp/qr_' + information.llave_permiso + '.png')
    except Exception:
        pass
    import base64
    encoded_string = ''
    with open("/tmp/permiso_%s.pdf" % (information.llave_permiso), "rb") as pdf:
        encoded_string = base64.b64encode(pdf.read())
        pdf.close()

    s3_client = boto3.client('s3')
    s3_client.upload_file("/tmp/permiso_%s.pdf" % (information.llave_permiso), 'igualauploads', "permiso_%s.pdf" % (information.llave_permiso))
    database.update('permisos_comerciales_descrip', 'llave_permiso', information.llave_permiso,
                    link_qr='http://s3-us-west-2.amazonaws.com/igualauploads/permiso_%s.pdf' % (information.llave_permiso))
    try:
        os.remove('/tmp/permiso_%s.pdf' % information.llave_permiso)
    except Exception:
        pass
    try:
        os.remove('/tmp/%s' % plantilla_file_name)
    except Exception:
        pass
    try:
        os.remove('/tmp/%s' % plantilla_file_name)
    except Exception:
        pass

    return encoded_string


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
                    ('horario_cierre', str),
                    ('link_identificacion_anv', str),
                    ('link_identificacion_rev', str),
                    ('dia_ini_funcionamiento', str),
                    ('dia_fin_funcionamiento', str)
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
                final_date = now_date + relativedelta(years=1)
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
                                vigencia_fin=final_date,
                                link_identificacion_anv=p.link_identificacion_anv,
                                link_identificacion_rev=p.link_identificacion_rev,
                                dia_ini_funcionamiento=p.dia_ini_funcionamiento,
                                dia_fin_funcionamiento=p.dia_fin_funcionamiento
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
                                id_ultima_modificacion=user_or_error.id,
                                link_identificacion_anv=p.link_identificacion_anv,
                                link_identificacion_rev=p.link_identificacion_rev,
                                dia_ini_funcionamiento=p.dia_ini_funcionamiento,
                                dia_fin_funcionamiento=p.dia_fin_funcionamiento


                                )
            database.update('contribuyentes_permisos_comerciales','id_permiso', p.id_permiso,
                            curp=p.curp,
                            rfc=p.rfc,
                            propietario_nombre=p.propietario_nombre,
                            propietario_apellidos=p.propietario_apellidos,
                            propietario_colonia=p.propietario_colonia,
                            propietario_calle_numero=p.propietario_calle_numero,
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
            if p.status_pago:
                response_b64 = create_pdf(p)
                return {
                    'headers': headers_cors,
                    'statusCode': 200,
                    'body': json.dumps({'file': response_b64.decode('utf-8')}),
                }
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



