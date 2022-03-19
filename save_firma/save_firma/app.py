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


def lambda_handler(event, context):
    """function to make a simple save licencia to app
    """
    from .db import Row
    b = json.loads(event['body'])
    body = Row(dict(b))
    expected = (('tipo', str),
                ('criterio',str),
                ('dato',str),
                ('link_firma',str)
            )
    from .utils import validate_body
    p = validate_body(expected,body)
    if isinstance(p,dict):
        if p.tipo == 'licencia':
            tabla = 'contribuyentes_licencias'
            exists = database.get('select curp, status_licencia from ' + tabla + ' where ' + p.criterio + '=%s', p.dato)
        else:
            tabla= 'permisos_comerciales_descrip'
            exists = database.get('select id_permiso, status_permiso from ' + tabla + ' where ' + p.criterio + '=%s', p.dato)

        if not exists:
            return {
                'headers':headers_cors,
                'statusCode': 400,
                'body': json.dumps({'message': 'Sin Resultados'})
            }
        if p.tipo == 'licencia':
            if exists.status_licencia:
                return {
                    'headers': headers_cors,
                    'statusCode': 400,
                    'body': json.dumps({'message': 'No es posible editar una licencia ya activada'})
                }
        else:
            if exists.status_permiso:
                return {
                    'headers': headers_cors,
                    'statusCode': 400,
                    'body': json.dumps({'message': 'No es posible editar un permiso ya activado'})
                }
        now_date = datetime.datetime.now(tz=timezone('America/Mexico_City')).date()
        now_hour = datetime.datetime.now(tz=timezone('America/Mexico_City')).time()
        if p.tipo == 'licencia':
            database.update('contribuyentes_licencias',p.criterio, p.dato,
                            link_firma=p.link_firma,
                            ultima_actualizacion_fecha=now_date,
                            ultima_actualizacion_hora=now_hour
                            )
        else:
            database.update('permisos_comerciales_descrip', p.criterio, p.dato,
                            link_firma=p.link_firma,
                            ultima_actualizacion_fecha=now_date,
                            ultima_actualizacion_hora=now_hour
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



