from utils import AttrDict

def validate_dict(params, param_specs):
    values = AttrDict()
    for s in param_specs:
        value = Exception # signals undefined
        for name_or_alias in [s.name] + s.aliases:
            if name_or_alias in params:
                value = params[name_or_alias]
        if value is not Exception: # param is defined
            if value == s.default: # bypass checks if already default (useful for None)
                values[s.name] = s.default
            else:
                values[s.name] = s.check(value)
        elif s.is_mandatory():
            raise ValidationError("Missing mandatory parameter '%s'." % s.name)
        else:
            values[s.name] = s.default
    return values

def validate_bottle_json_body():
    try:
        if not request.content_type.startswith('application/json'):
            raise HTTPError(400, "Invalid request.  Content-Type must be set to \'application/json\'.")
        if request.json is None or not isinstance(request.json, dict):
            raise HTTPError(400, "Invalid request.  Expected JSON-formatted input parameters in request body.")
    except ValueError, e:
        raise  HTTPError(400, "Invalid request.  Error parsing JSON body: %s" % e)

def validate_bottle_json_post(*param_specs):
    if not param_specs: return
    validate_bottle_json_body()
    try:
        return validate_dict(request.json, param_specs)
    except ValidationError, e:
        raise HTTPError(400, u"Invalid request.  %s" % e)

def validate_bottle(*param_specs, method='POST'):
    if method == 'POST':
        return validate_bottle_json_post(*param_specs)
    elif method == 'GET':
        return validate_bottle_get(*param_specs)