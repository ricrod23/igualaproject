from .db import get_db

import json
import hashlib

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

def encode_rows(rows, encoding):
    for r in rows:
        final = ''
        for i in range(len(r)):
            if isinstance(r[i], str):
                final += r[i].encode('utf-8').decode()
        r = final
    return rows

def rows_to_csv(rows, delimiter=None):
    from io import StringIO
    import csv
    fixup_delimiter = None
    if delimiter and ord(delimiter) > 127:
        fixup_delimiter = delimiter.encode('utf-8')
        delimiter = chr(1)
    rows = encode_rows(rows, 'utf-8')
    dialect='excel'
    if delimiter:
        class AlternateDialect(csv.excel): pass
        AlternateDialect.delimiter = delimiter
        dialect = AlternateDialect
    csv_out = StringIO()
    csv_writer = csv.writer(csv_out, dialect=dialect)
    csv_writer.writerows(rows)
    content = csv_out.getvalue()
    if fixup_delimiter:
        content = content.replace(delimiter, fixup_delimiter)
    return content


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
        from .db import Row
        b = event['queryStringParameters']
        body = Row(b)
        expected = (('meses_vencimiento',str),
                    ('activos', str),
                    ('tipo', str),
                    ('excel', str)
        )
        from .utils import validate_body
        p = validate_body(expected,body)
        if isinstance(p,dict):
            where_clause = ' where 1 = 1 '
            args =[]
            if p.tipo == 'licencia':
                if int(p.meses_vencimiento)>0:
                    where_clause += ' AND vigencia_fin <= (now()+INTERVAL %s MONTH) '
                    args.append(p.meses_vencimiento)
                if p.activos in ['1','0']:
                    where_clause += ' AND status_licencia = %s '
                    args.append(p.activos)
                info = database.query('''select cl.id_contribuyente, curp, cl.nombre, cl.apellidos, calle_numero,colonia,municipio,estado,cp,telefono_celular, email, tipo_sangre,
                 alergias, tipo_licencia,CAST(vigencia_inicio AS CHAR) as vigencia_inicio, CAST(vigencia_fin AS CHAR) as vigencia_fin, fecha_nacimiento, sexo, link_firma, telefono_fijo, status_pago, alergias_descripcion, donante, tipo_licencia, link_foto, status_licencia
                from contribuyentes_licencias as cl '''+ where_clause, *args)

                info_headers = [
                    ['id_contribuyente', 'curp', 'nombre', 'apellidos', 'calle_numero',
                     'colonia', 'cp', 'telefono_celular', 'telefono_fijo', 'email', 'vigencia_inicio', 'vigencia_fin']]

            elif p.tipo == 'permisos':
                if int(p.meses_vencimiento) > 0:
                    where_clause += ' AND vigencia_fin <= (now()+INTERVAL %s MONTH) '
                    args.append(p.meses_vencimiento)
                if p.activos in ['1','0']:
                    where_clause += ' AND status_permiso = %s '
                    args.append(p.activos)
                info = database.query('''select pd.id_permiso, razon_social, denominacion, comercio_calle_numero, comercio_colonia, comercio_cp, giro, tipo, horario_inicio, 
                horario_cierre, status_permiso, status_pago, curp, rfc, propietario_nombre, propietario_apellidos, propietario_colonia, propietario_cp, telefono_celular,
                telefono_fijo, email, fecha_nacimiento, sexo, CAST(vigencia_inicio AS CHAR) as vigencia_inicio, CAST(vigencia_fin AS CHAR) as vigencia_fin
                from permisos_comerciales_descrip pd  inner join contribuyentes_permisos_comerciales cp on cl.id_contribuyente = cp.id_contribuyente  ''' + where_clause, *args)
                info_headers = [
                    ['id_permiso', 'razon_social', 'denominacion', 'comercio_calle_numero', 'comercio_colonia',
                     'comercio_cp', 'giro', 'tipo',
                     'horario_inicio', 'horario_cierre', 'status_permiso', 'curp', 'rfc', 'propietario_nombre',
                     'propietario_apellidos', 'telefono_ceular', 'telefono_fijo', 'email','vigencia_inicio','vigencia_fin']]
            else:
                if int(p.meses_vencimiento) > 0:
                    where_clause += ' AND vigencia_fin <= (now()+INTERVAL %s MONTH) '
                    args.append(p.meses_vencimiento)
                if p.activos in ['1', '0']:
                    where_clause += ' AND status_permiso = %s '
                    args.append(p.activos)
                info1 = database.query('''select pd.id_permiso, razon_social, denominacion, comercio_calle_numero, comercio_colonia, comercio_cp, giro, tipo, horario_inicio, 
                horario_cierre, status_permiso, status_pago, curp, rfc, propietario_nombre, propietario_apellidos, propietario_colonia, propietario_cp, telefono_celular,
                telefono_fijo, email, fecha_nacimiento, sexo, CAST(vigencia_inicio AS CHAR) as vigencia_inicio, CAST(vigencia_fin AS CHAR) as vigencia_fin
                from permisos_comerciales_descrip pd  inner join contribuyentes_permisos_comerciales cp on pd.id_permiso = cp.id_permiso  ''' + where_clause,*args)

                info2 = database.query('''select cl.id_contribuyente, curp, cl.nombre, cl.apellidos, calle_numero,colonia,municipio,estado,cp,telefono_celular, email, tipo_sangre,
                                 alergias, tipo_licencia, fecha_nacimiento, sexo, link_firma, telefono_fijo, status_pago, alergias_descripcion, donante, 
                                 tipo_licencia, link_foto, status_licencia, CAST(vigencia_inicio AS CHAR) as vigencia_inicio, CAST(vigencia_fin AS CHAR) as vigencia_fin
                                from contribuyentes_licencias as cl ''' + where_clause, *args)
                info = info1+info2
                info_headers = [
                    ['id_permiso', 'razon_social', 'denominacion', 'comercio_calle_numero', 'comercio_colonia',
                     'comercio_cp', 'giro', 'tipo',
                     'horario_inicio', 'horario_cierre', 'status_permiso', 'curp', 'rfc', 'propietario_nombre',
                     'propietario_apellidos', 'telefono_ceular', 'telefono_fijo', 'email', 'vigencia_inicio',
                     'vigencia_fin','id_contribuyente', 'curp', 'nombre', 'apellidos', 'calle_numero',
                     'colonia', 'cp', 'telefono_celular', 'telefono_fijo', 'email', 'vigencia_inicio', 'vigencia_fin']]

            if info:
                if p.excel == 'true':
                    import datetime
                    from pytz import timezone
                    now_hour = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
                    filename = 'reporte_%s_%s.csv' % ('iguala_gob', now_hour.strftime('%y-%m-%d'))
                    for t in info:
                        info_headers.append([t[i] if i in t else '' for i in info_headers[0]])
                    info_csv = rows_to_csv(info_headers)
                    headers_cors["Content-Type"]= "application/octet-stream"
                    headers_cors["Content-Disposition"]= 'attachment; filename="%s"' % filename
                    return {
                        'headers': headers_cors,
                        'statusCode': 200,
                        'body': info_csv
                    }
                else:

                    return {
                        'headers': headers_cors,
                        'statusCode': 200,
                        'body': json.dumps(info)
                     }
            else:
                return {
                    'headers': headers_cors,
                    'statusCode': 400,
                    'body': json.dumps({'message': 'No existe informacion con los datos proporcionados'})
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



