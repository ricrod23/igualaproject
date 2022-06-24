from .db import get_db

import json
import hashlib
import datetime
import random
from pytz import timezone
import boto3
from reportlab.lib.utils import ImageReader

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

def create_pdf_anv(id_contr):
    import os
    import io

    from PyPDF2 import PdfFileReader, PdfFileWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    information = database.get('''select id_contribuyente, nombre, apellidos, curp, vigencia_inicio, vigencia_fin, 
     calle_numero, colonia, cp, tipo_licencia, link_firma, link_foto, llave_licencia from contribuyentes_licencias where id_contribuyente= %s ''', id_contr)
    # get image
    s3 = boto3.client(
        aws_access_key_id='AKIAUAAEXHS5LFZSLGZC',
        aws_secret_access_key='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',
        region_name='us-west-2',
        service_name='s3'
    )

    qr_file_name = 'qr_' + information.llave_licencia + '.png'
    plantilla_file_name = 'plantilla_licencia_iguala_anv_v2.pdf'

    with open('/tmp/' + qr_file_name, 'wb') as data:
       s3.download_fileobj('igualauploads', qr_file_name, data)
    with open('/tmp/' + plantilla_file_name, 'wb') as data:
        s3.download_fileobj('igualauploads', plantilla_file_name, data)

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    image_profile = ImageReader(information.link_foto)
    firma_image = ImageReader(information.link_firma)
    can.drawImage(image_profile,10,510,50,50)
    can.drawImage(firma_image, 10, 471, 50, 30, mask='auto')
    if information.tipo_licencia == 'AUTOMOVILISTA':
        tipo_letra = 'A_roja.png'
    elif information.tipo_licencia == 'CHOFER':
        tipo_letra = 'C_roja.png'
    elif information.tipo_licencia == 'PERMISO':
        tipo_letra = 'P_roja.png'
    elif information.tipo_licencia == 'MOTOCICLISTA':
        tipo_letra = 'M_roja.png'

    with open('/tmp/' + tipo_letra, 'wb') as data:
       s3.download_fileobj('igualauploads', tipo_letra, data)

    can.drawImage('/tmp/' + tipo_letra, 201, 533, 25, 25)
    can.drawImage('/tmp/qr_' + information.llave_licencia + '.png', 200, 485, 35, 35)
    can.setFont('Helvetica-Bold', 5)
    can.drawString(72, 565, "NOMBRE:")
    can.setFont('Helvetica-Bold', 8)
    can.drawString(72, 556, information.nombre)
    can.drawString(72, 547, information.apellidos)
    can.setFont('Helvetica-Bold', 5)
    can.drawString(72, 537, 'CURP: %s'%information.curp)
    can.drawString(72, 527, 'DOMICILIO:')
    can.drawString(72, 520,'%s, %s'% (information.calle_numero,information.colonia))
    can.drawString(72, 513, 'IGUALA DE LA INDEPENDENCIA, GUERRERO, %s' % (information.cp))
    can.drawString(72, 503, 'EXPEDICIÓN:')
    can.drawString(72, 496, '%s' % information.vigencia_inicio.strftime('%Y-%m-%d'))
    can.drawString(72, 486, 'VENCIMIENTO:')
    can.drawString(72, 479, '%s' % information.vigencia_fin.strftime('%Y-%m-%d'))

    can.setFont('Helvetica-Bold', 7)
    can.drawString(160, 503, 'FOLIO:')
    can.drawString(163, 496, '%s' % information.id_contribuyente)
    can.drawString(158, 478, '%s' % information.tipo_licencia)
    #
    can.save()

    # move to the beginning of the StringIO buffer
    packet.seek(0)

    # create a new PDF with Reportlab
    new_pdf = PdfFileReader(packet)
    # read your existing PDF
    read_plantilla = open("/tmp/plantilla_licencia_iguala_anv_v2.pdf", "rb")
    existing_pdf = PdfFileReader(read_plantilla)
    output = PdfFileWriter()
    # add the "watermark" (which is the new pdf) on the existing page
    page = existing_pdf.getPage(0)
    page.mergePage(new_pdf.getPage(0))
    output.addPage(page)
    # finally, write "output" to a real file
    outputStream = open("/tmp/licencia_%s_anv.pdf" % (information.llave_licencia), "wb")
    output.write(outputStream)
    outputStream.close()
    read_plantilla.close()

    try:
        os.remove('/tmp/qr_' + information.llave_licencia + '.png')
    except Exception:
        pass
    try:
        os.remove('/tmp/' + tipo_letra)
    except Exception:
        pass
    import base64
    with open("/tmp/licencia_%s_anv.pdf" % (information.llave_licencia), "rb") as pdf:
        encoded_string = base64.b64encode(pdf.read())
        pdf.close()

    s3.upload_file("/tmp/licencia_%s_anv.pdf" % (information.llave_licencia), 'igualauploads',
                          "licencia_%s_anv.pdf" % (information.llave_licencia))
    try:
        os.remove('/tmp/licencia_%s_anv.pdf' % information.llave_licencia)
    except Exception:
        pass
    try:
        os.remove('/tmp/%s' % plantilla_file_name)
    except Exception:
        pass

    return encoded_string

def create_pdf_rev(id_contr):
    import os
    import io

    from PyPDF2 import PdfFileReader, PdfFileWriter
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter

    information = database.get('''select fecha_nacimiento, donante, telefono_contacto, ce.nombre as nombre_emergencia, ce.apellidos as apellidos_emergencia, tipo_sangre, alergias_descripcion, llave_licencia 
    from contribuyentes_licencias cl inner join contactos_emergencia ce on cl.id_contribuyente = ce.id_contribuyente where cl.id_contribuyente= %s ''', id_contr)
    # get image
    s3 = boto3.client(
        aws_access_key_id='AKIAUAAEXHS5LFZSLGZC',
        aws_secret_access_key='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',
        region_name='us-west-2',
        service_name='s3'
    )

    qr_file_name = 'qr_' + information.llave_licencia + '.png'
    plantilla_file_name = 'plantilla_licencia_iguala_rev_v2.pdf'

    with open('/tmp/' + qr_file_name, 'wb') as data:
       s3.download_fileobj('igualauploads', qr_file_name, data)
    with open('/tmp/' + plantilla_file_name, 'wb') as data:
        s3.download_fileobj('igualauploads', plantilla_file_name, data)

    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=letter)
    can.drawImage('/tmp/qr_' + information.llave_licencia + '.png', 170, 510, 70, 70)
    can.setFont('Helvetica-Bold', 5)
    can.drawString(5, 600, "FECHA DE NACIMIENTO: %s" % information.fecha_nacimiento)
    can.drawString(5, 590, 'DONADOR DE ÓRGANOS: %s'%('SÍ' if information.donante else 'NO'))
    can.drawString(5, 580, 'TELEFONO EN CASO DE EMRGENCIA:')
    can.drawString(5, 570,'%s'% information.telefono_contacto)
    can.drawString(5, 560, 'CONTACTO DE EMERGENCIA:')
    can.drawString(5, 550, '%s %s' %(information.nombre_emergencia, information.apellidos_emergencia))
    can.drawString(5, 540, 'TIPO DE SANGRE: %s' % information.tipo_sangre)
    can.drawString(5, 530, 'ALERGÍAS:')
    can.drawString(5, 520, '%s' % information.alergias_descripcion)
    #
    can.save()

    # move to the beginning of the StringIO buffer
    packet.seek(0)

    # create a new PDF with Reportlab
    new_pdf = PdfFileReader(packet)
    # read your existing PDF
    read_plantilla = open("/tmp/%s"%plantilla_file_name, "rb")
    existing_pdf = PdfFileReader(read_plantilla)
    output = PdfFileWriter()
    # add the "watermark" (which is the new pdf) on the existing page
    page = existing_pdf.getPage(0)
    page.mergePage(new_pdf.getPage(0))
    output.addPage(page)
    # finally, write "output" to a real file
    outputStream = open("/tmp/licencia_%s_rev.pdf" % (information.llave_licencia), "wb")
    output.write(outputStream)
    outputStream.close()
    read_plantilla.close()

    try:
        os.remove('/tmp/qr_' + information.llave_licencia + '.png')
    except Exception:
        pass
    import base64
    with open("/tmp/licencia_%s_rev.pdf" % (information.llave_licencia), "rb") as pdf:
        encoded_string = base64.b64encode(pdf.read())
        pdf.close()

    s3.upload_file("/tmp/licencia_%s_rev.pdf" % (information.llave_licencia), 'igualauploads',
                          "licencia_%s_rev.pdf" % (information.llave_licencia))
    try:
        os.remove('/tmp/licencia_%s_rev.pdf' % information.llave_licencia)
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
        expected = (('calle_numero', str),
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
                    ('link_foto', str),
                    ('status_licencia', bool),
                    ('status_pago', bool),
                    ('folio_pago', str),
                    ('link_identificacion_anv', str),
                    ('link_identificacion_rev', str),
                    ('link_certificado_tipo_sangre', str),
                    ('link_curp', str),
                    ('link_acta', str),
                    ('link_comp_domicilio', str)
                )
        from .utils import validate_body
        p = validate_body(expected,body)
        if isinstance(p,dict):
            exists = database.get('select curp, status_licencia from contribuyentes_licencias where curp =%s', p.curp.upper())
            if not exists:
                return {
                    'headers':headers_cors,
                    'statusCode': 400,
                    'body': json.dumps({'message': 'Licencia no encontrada'})
                }
            if exists.status_licencia:
                return {
                    'headers': headers_cors,
                    'statusCode': 400,
                    'body': json.dumps({'message': 'No es posible editar una licencia ya activada'})
                }
            now_date = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
            now_hour = datetime.datetime.now(tz=timezone('America/Mexico_City')).time()
            if p.status_licencia or p.status_pago:
                if not p.status_pago or not p.status_licencia:
                    return {
                        'headers': headers_cors,
                        'statusCode': 400,
                        'body': json.dumps({'message': 'Error con estatus de pago o estatus de licencia'})
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
                database.update('contribuyentes_licencias', 'curp', p.curp,
                                calle_numero=p.calle_numero,
                                colonia=p.colonia,
                                municipio=p.municipio,
                                estado=p.estado,
                                cp=p.cp,
                                telefono_celular=p.telefono_celular,
                                telefono_fijo=p.telefono_fijo,
                                email=p.email,
                                tipo_sangre=p.tipo_sangre,
                                alergias=p.alergias,
                                donante=p.donante,
                                alergias_descripcion=p.alergias_descripcion,
                                tipo_licencia=p.tipo_licencia,
                                link_foto=p.link_foto,
                                ultima_actualizacion_fecha=now_date,
                                ultima_actualizacion_hora=now_hour,
                                id_ultima_modificacion=user_or_error.id,
                                status_licencia=True,
                                status_pago=True,
                                folio_pago=p.folio_pago,
                                vigencia_inicio=now_date,
                                vigencia_fin=final_date,
                                link_identificacion_anv = p.link_identificacion_anv,
                                link_identificacion_rev= p.link_identificacion_rev,
                                link_certificado_tipo_sangre=p.link_certificado_tipo_sangre,
                                link_curp=p.link_curp,
                                link_acta=p.link_acta,
                                link_comp_domicilio=p.link_comp_domicilio
                )
            else:
                database.update('contribuyentes_licencias','curp', p.curp,
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
                                alergias_descripcion =p.alergias_descripcion,
                                tipo_licencia=p.tipo_licencia,
                                link_foto=p.link_foto,
                                ultima_actualizacion_fecha=now_date,
                                ultima_actualizacion_hora=now_hour,
                                id_ultima_modificacion=user_or_error.id,
                                status_licencia=False,
                                status_pago=False,
                                link_identificacion_anv=p.link_identificacion_anv,
                                link_identificacion_rev=p.link_identificacion_rev,
                                folio_pago='',
                                link_certificado_tipo_sangre=p.link_certificado_tipo_sangre,
                                link_curp=p.link_curp,
                                link_acta=p.link_acta,
                                link_comp_domicilio=p.link_comp_domicilio
                            )
            id = database.get('select id_contribuyente from contribuyentes_licencias where curp = %s',p.curp.upper()).id_contribuyente
            database.update('contactos_emergencia', 'id_contribuyente',id,
                            nombre = p.nombre_emergencia,
                            apellidos = p.apellidos_emergencia,
                            telefono_contacto = p.telefono_emergencia
                        )
            if p.status_pago:
                file1 = create_pdf_anv(id)
                file2 = create_pdf_rev(id)
                return {
                    'headers': headers_cors,
                    'statusCode': 200,
                    'body': json.dumps(
                        {
                            'file_anv': file1.decode('utf-8'),
                            'file_rev': file2.decode('utf-8')
                        }
                    )
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



