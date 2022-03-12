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
                ('dato', str)
            )
    from .utils import validate_body
    p = validate_body(expected,body)
    if isinstance(p,dict):
        info = database.get('''select id_contribuyente, curp, nombre, apellidos, alergias_descripcion, donante, tipo_licencia, link_foto, vigencia_inicio, vigencia_fin, status_licencia
                                from contribuyentes_licencias where ''' + p.criterio +'''= %s''', p.dato)
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



