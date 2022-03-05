import time
import mysql.connector
from mysql.connector.conversion import MySQLConverter

IntegrityError = mysql.connector.IntegrityError


class MySQLBoolAwareConverter(MySQLConverter):
    def _TINY_to_python(self, value, desc=None):
        return bool(int(value))


class Connection(object):
    def __init__(self, host, database, user, password):
        self.c = None
        self.args = {
            'host': host,
            'database': database,
            'user': user,
            'password': password,
            'autocommit': True,
            'buffered': True,
            'sql_mode': 'TRADITIONAL',
            'time_zone': '+0:00',
            'converter_class': MySQLBoolAwareConverter,
        }
        self.max_idle_time = 1 * 60 * 60
        self.last_use_time = 0
        self.ensure_connected()

    def close(self):
        if getattr(self, "c", None) is not None:
            self.c.close()
            self.c = None

    def __del__(self):
        try:
            self.close()
        except Exception:  # sometime get weird attribute errors on shutdown
            pass

    def reconnect(self):
        """Closes the existing database connection and re-opens it."""
        self.close()
        self.c = mysql.connector.connect(**self.args)

    def ensure_connected(self):
        # Mysql by default closes client connections that are idle for
        # 8 hours, but the client library does not report this fact until
        # you try to perform a query and it fails.  Protect against this
        # case by preemptively closing and reopening the connection
        # if it has been idle for too long (1 hour by default).
        idle_time = time.time() - self.last_use_time
        if self.c is None or idle_time > self.max_idle_time or not self.c.is_connected():
            self.reconnect()
        self.last_use_time = time.time()

    def cursor(self, buffered=True):
        self.ensure_connected()
        if not buffered:
            from mysql.connector.cursor import MySQLCursor
            return MySQLCursor(self.c)
        return self.c.cursor()

    def _execute(self, cursor, query, parameters, kwparameters):
        try:
            info = cursor.execute(query, kwparameters or parameters)
            return info
        except mysql.connector.OperationalError:
            self.close()
            cursor.close()
            raise

    def query_unbuffered(self, query, *parameters, **kwparameters):
        """Returns a row list for the given query and parameters."""
        cursor = self.cursor(buffered=False)
        try:
            self._execute(cursor, query, parameters, kwparameters)
            column_names = [d[0] for d in cursor.description]
            for row in cursor:
                yield Row(dict(zip(column_names, row)))
        finally:
            cursor.close()
            self.close()

    def query(self, query, *parameters, **kwparameters):
        """Returns a row list for the given query and parameters."""
        cursor = self.cursor()
        try:
            self._execute(cursor, query, parameters, kwparameters)
            column_names = [d[0] for d in cursor.description]
            info = [Row(dict(zip(column_names, row))) for row in cursor]
            self.close()
            return info
        finally:
            self.close()

    def get(self, query, *parameters, **kwparameters):
        """Returns the first row returned for the given query."""
        rows = self.query(query, *parameters, **kwparameters)
        self.close()
        if not rows:
            return None
        elif len(rows) > 1:
            raise Exception("Multiple rows returned for Database.get() query")
        else:
            return rows[0]

    def execute_lastrowid(self, query, *parameters, **kwparameters):
        """Executes the given query, returning the lastrowid from the query."""
        cursor = self.cursor()
        try:
            self._execute(cursor, query, parameters, kwparameters)
            return cursor.lastrowid
        finally:
            cursor.close()
            self.close()

    execute = execute_lastrowid

    def execute_many(self, query, *parameters, **kwparameters):
        """Executes the given query on multiple rows of data."""
        cursor = self.cursor()
        try:
            info = cursor.executemany(query, *parameters, **kwparameters)
            return info
        finally:
            cursor.close()
            self.close()

    def insert(self, table_name, **kwargs):
        if not kwargs: return
        fields, values = zip(*kwargs.items())
        field_set = '(' + ','.join(['`%s`' % f for f in fields]) + ')'
        value_set = '(' + ','.join(['%s'] * len(fields)) + ')'
        sql = 'INSERT INTO `%s` %s VALUES %s' % (table_name, field_set, value_set)
        return self.execute_lastrowid(sql, *values)

    def replace(self, table_name, **kwargs):
        if not kwargs: return
        fields, values = zip(*kwargs.items())
        field_set = '(' + ','.join(['`%s`' % f for f in fields]) + ')'
        value_set = '(' + ','.join(['%s'] * len(fields)) + ')'
        sql = 'REPLACE INTO `%s` %s VALUES %s' % (table_name, field_set, value_set)
        return self.execute_lastrowid(sql, *values)

    def update(self, table_name, key_name, key_value, **kwargs):
        if not kwargs: return
        fields, values = zip(*kwargs.items())
        sql = 'UPDATE `%s` SET ' % table_name
        sql += ','.join(' %s=%%s ' % f for f in fields)
        sql += ' WHERE %s=%%s LIMIT 1' % key_name  # use limit 1 for safety for now
        args = list(values) + [key_value]
        return self.execute(sql, *args)


class Row(dict):
    """A dict that allows for object-like property access syntax."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

def get_db():
    return Connection('municipio-iguala.cszxcprpucjo.us-east-1.rds.amazonaws.com','iguala_db','root','qHj=p8$7wGuz4pz!')