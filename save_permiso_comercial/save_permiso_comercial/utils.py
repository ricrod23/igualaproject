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

def send_outlook(recipients, subject, body, files=[], sender=None):
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email.utils import formatdate
    from email import encoders
    import smtplib

    if not recipients:
        return
    if not isinstance(recipients, list):
        recipients = [recipients]

    outlook_sender = 'permisoslicenciasigualagro@gmail.com'
    outlook_username = 'permisoslicenciasigualagro'
    outlook_password = 'Licencias2022'

    msg = MIMEMultipart()
    msg['From'] = 'permisoslicenciasigualagro@gmail.com'
    msg['To'] = ','.join(recipients)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    msg.attach(MIMEText(body.encode('utf-8'), 'plain', 'UTF-8'))

    for filename, content, mime_type in files:
        part = MIMEBase('application', mime_type)
        part.set_payload(content)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', 'attachment; filename="%s"' % filename)
        msg.attach(part)

    smtp = smtplib.SMTP('smtp.gmail.com', 587)
    smtp.ehlo()
    smtp.starttls()
    smtp.ehlo()
    smtp.login(outlook_username, outlook_password)
    smtp.sendmail(outlook_sender, recipients, msg.as_string())
    smtp.close()