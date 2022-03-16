class AttrDict(dict):
    """A dictionary with attribute-style access. It maps attribute access to
    the real dictionary.  """

    def _init_(self, *args, **kwargs):
        dict._init_(self, *args, **kwargs)

    def _getstate_(self):
        return self._dict_.items()

    def _setstate_(self, items):
        for key, val in items:
            self._dict_[key] = val

    def _repr_(self):
        return "%s(%s)" % (self._class.name, dict.repr_(self))

    def _setitem_(self, key, value):
        return super(AttrDict, self)._setitem_(key, value)

    def _getitem_(self, name):
        return super(AttrDict, self)._getitem_(name)

    def _delitem_(self, name):
        return super(AttrDict, self)._delitem_(name)

    _getattr_ = _getitem_
    _setattr_ = _setitem_

    def copy(self):
        return AttrDict(self)

    def _asdict(self):
        """Method used by simplejson."""
        return self


def validate_body(tuples, body):
    for t in tuples:
        if t[0] not in [k for k in body.keys()]:
            return 'Falta elemento %s en peticion' % t[0]

    for b in body:
        for t in tuples:
            if b == t[0]:
                if type(body[b]) is not t[1]:
                    return 'Elementp %s debe ser de typo %s' %(b,str(t[1]))

    return body


def ms():
    import time
    return int(time.time() * 1000)


def ms_to_datetime(unixtime_ms, timezone='UTC'):
    import datetime
    from dateutil.zoneinfo import gettz
    tz = gettz(timezone)
    return datetime.datetime.fromtimestamp(unixtime_ms/1000.0, tz)

def format_ms(unixtime_ms=None, format='%Y-%m-%d %H:%M:%S', timezone='UTC'):
    if not unixtime_ms:
        unixtime_ms = ms()
    return ms_to_datetime(unixtime_ms, timezone).strftime(format)



