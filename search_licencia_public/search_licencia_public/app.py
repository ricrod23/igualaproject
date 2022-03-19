from .db import get_db

import json
import hashlib

headers_cors = {
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "*"
}

database = get_db()


def lambda_handler(event, context):
    """function to make a simple save licencia to app
    """
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
            info = database.get('''select id_contribuyente, curp, nombre, apellidos, alergias_descripcion, donante, tipo_licencia, link_foto, CAST(vigencia_inicio AS CHAR) as vigencia_inicio,
            CAST(vigencia_fin AS CHAR) as vigencia_fin, status_licencia
                                    from contribuyentes_licencias where ''' + p.criterio +'''= %s''', p.dato)
            if info:
                import datetime
                from pytz import timezone
                now_date = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
                if info.vigencia_fin:
                    if now_date > datetime.datetime.strptime(info.vigencia_fin, '%Y-%m-%d').date():
                        database.update('contribuyentes_licencia', p.criterio, p.dato, status_licencia=False)
                        p.status_licencia= False
        else:
            info = database.query('''select cp.id_permiso, razon_social, denominacion, giro, tipo, horario_inicio, horario_cierre, status_permiso, 
            CAST(vigencia_inicio AS CHAR) as vigencia_inicio, CAST(vigencia_fin AS CHAR) as vigencia_fin, curp, rfc, propietario_nombre, propietario_apellidos
                                                from permisos_comerciales_descrip pd  inner join contribuyentes_permisos_comerciales cp on pd.id_permiso = cp.id_permiso where ''' + p.criterio + '''= %s''',p.dato)
            if info:
                import datetime
                from pytz import timezone
                now_date = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
                if info.vigencia_fin:
                    if now_date > datetime.datetime.strptime(info.vigencia_fin, '%Y-%m-%d').date():
                        database.update('permisos_comerciales_descrip', p.criterio, p.dato, status_permiso=False)
                        p.status_permiso= False
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



