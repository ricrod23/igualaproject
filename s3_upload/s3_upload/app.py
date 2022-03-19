from .db import get_db

import json
import hashlib

database = get_db()

headers_cors = {
        "Access-Control-Allow-Headers": "*",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "*"
}


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


def get_s3_form(bucket, region, aws_access_key, aws_secret, acl='private'):
    import hashlib
    import hmac
    import json
    import base64
    from .utils import format_ms, ms

    algorithm = 'AWS4-HMAC-SHA256'
    service = 's3'
    long_date = format_ms(format='%Y%m%dT%H%M%SZ')
    short_date = format_ms(format='%Y%m%d')
    request_type = 'aws4_request'
    expires = str(60 * 60 * 24)
    success_status = str(201)
    url = 'https://s3-%s.amazonaws.com/%s/' % (region, bucket)

    credentials = '/'.join([
        aws_access_key,
        short_date,
        region,
        service,
        request_type,
    ])

    policy = {
        'expiration': format_ms(ms() + 1000 * 60 * 6, format='%Y-%m-%dT%H:%M:%SZ'),
        'conditions': [
            {'bucket': bucket},
            {'acl': acl},
            ['starts-with', '$key', ''],
            ['starts-with', '$Content-Type', ''],
            {'success_action_status': success_status},
            {'x-amz-credential': credentials},
            {'x-amz-algorithm': algorithm},
            {'x-amz-date': long_date},
            {'x-amz-expires': expires},
        ]
    }
    base64_policy = base64.b64encode(json.dumps(policy).strip().encode('utf-8')).decode()
    import functools
    parts = [b'AWS4' + aws_secret.encode('utf-8'), short_date, region, service, request_type, base64_policy]
    signature = functools.reduce(
        lambda k, v: hmac.new(k, v.encode('utf-8'), hashlib.sha256).digest(), parts).hex()

    inputs = {
        'Content-Type': '',
        'acl': acl,
        'success_action_status': success_status,
        'policy': base64_policy,
        'X-amz-credential': credentials,
        'X-amz-algorithm': algorithm,
        'X-amz-date': long_date,
        'X-amz-expires': expires,
        'X-amz-signature': signature,
    }

    return url, inputs


def lambda_handler(event, context):
    """function to make a simple save licencia to app
    """
    import base64
    from .db import Row
    headers = Row(dict(event['headers']))
    if not 'Authorization' in headers:
        return {
            'headers':headers_cors,
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

    url, s3_form = get_s3_form(
        'igualauploads',
        'us-west-2',
        'AKIAUAAEXHS5LFZSLGZC',
        'stKvf09rH4gxJvrujzsHpxbW9wV1mv0X2LAk84dr',
        'public-read')
    return {
        'headers': headers_cors,
        'statusCode': 200,
        'body': json.dumps({'url': url, 's3_form': s3_form})
    }



