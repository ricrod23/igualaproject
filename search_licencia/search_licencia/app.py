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
        expected = (('criterio',str),
                    ('dato', str),
                    ('tipo', str)
        )
        from .utils import validate_body
        p = validate_body(expected,body)
        if isinstance(p,dict):
            if p.tipo == 'licencia':
                info = database.get('''select cl.id_contribuyente, curp, cl.nombre, cl.apellidos, calle_numero,colonia,municipio,estado,cp,telefono_celular, email, tipo_sangre,
                 alergias, tipo_licencia, fecha_nacimiento, sexo, link_firma, telefono_fijo, status_pago, alergias_descripcion, donante, tipo_licencia, link_foto, status_licencia,
                 ce.nombre as nombre_emergencia, ce.apellidos as apellidos_emergencia, telefono_contacto as telefono_emergencia
                from contribuyentes_licencias as cl inner join contactos_emergencia as ce on cl.id_contribuyente = ce.id_contribuyente 
                where ''' + p.criterio +'''= %s''', p.dato)
            else:
                info = database.query('''select cp.id_permiso, razon_social, denominacion, giro, tipo, horario_inicio, horario_cierre, status_permiso, 
                CAST(vigencia_inicio AS CHAR) as vigencia_inicio, CAST(vigencia_fin AS CHAR) as vigencia_fin, curp, rfc, propietario_nombre, propietario_apellidos
                                                    from permisos_comerciales_descrip pd  inner join contribuyentes_permisos_comerciales cp on pd.id_permiso = cp.id_permiso where ''' + p.criterio + '''= %s''',p.dato)
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



