from pylons import c

class DatabaseRouter(object):
    '''A router to control all database operations on Django models'''

    def db_for_read(self, model, **hints):
        if c.app: return c.app.db_name
        return None

    def db_for_write(self, model, **hints):
        if c.app: return c.app.db_name
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return True

    def allow_syncdb(self, db, model):
        return True

