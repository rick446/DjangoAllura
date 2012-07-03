from pylons import c
from allura import model as M

import ming.odm
from ming import gql
from ming import schema as S
from ming.odm.declarative import MappedClass

from . import users

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

class _ModelMeta(MappedClass.__metaclass__):

    def __new__(meta, name, bases, dct):
        mm = dct.get('__mongometa__')
        if not mm:
            class __mongometa__: pass
            dct['__mongometa__'] = mm = __mongometa__
        if '_id' not in dct:
            dct['_id'] = ming.odm.FieldProperty(S.ObjectId)
        mm.name = name
        cls = MappedClass.__metaclass__.__new__(meta, name, bases, dct)
        cls._model_by_collection_name[name] = cls
        cls._meta = _DjangoMeta(cls)
        return cls

class _DjangoMeta(object):

    def __init__(self, cls):
        self._cls = cls
        self._mapper = cls.query.mapper

    @property
    def fields(self):
        return []

    @property
    def many_to_many(self):
        return []

class Model(MappedClass):
    __metaclass__ = _ModelMeta
    _model_by_collection_name = {}
    class __mongometa__:
        session = M.project_orm_session

    class DoesNotExist(Exception): pass

    def key(self):
        return self._id

    def put(self):
        pass # objects are automatically flushed with Ming

    @classmethod
    def all(cls):
        return ModelQuery(cls)

    @classmethod
    def get(cls, key_or_keys):
        if isinstance(key_or_keys, (list, set)):
            return cls.query.find(dict(
                    _id={'$in': list(key_or_keys)})).all()
        else:
            return cls.query.get(_id=key_or_keys)

    @classmethod
    def get_or_insert(cls, key, **kwargs):
        result = cls.get(key)
        if result is None:
            result = cls(_id=key, **kwargs)
        return result

    @classmethod
    def kind(cls):
        return cls.__name__

    @classmethod
    def get_by_key_name(cls, keys, parent=None):
        single = False
        # if keys isn't a list then a single instance is returned
        if not isinstance(keys, (list, tuple)):
            single = True
            keys = [keys]
        result = []
        for key in keys:
            try:
                kwds = {'gae_key': str(key)}
                if parent is not None:
                    kwds['gae_ancestry__icontains'] = str(parent.key())
                result.append(cls.query.get(**kwds))
            except cls.DoesNotExist:
                result.append(None)
        if single and len(result) != 0:
            return result[0]
        elif single:
            return None
        else:
            return result

    @classmethod
    def gql(cls, gql_text, *args, **kwargs):
        pymongo_cursor = gql.gql_filter(
            cls.query.mapper.collection.m.collection,
            gql_text, *args, **kwargs)
        ming_cursor = ming.Cursor(cls.query.mapper.collection, pymongo_cursor)
        odm_cursor = ming.odm.odmsession.ODMCursor(
            M.project_orm_session,
            cls, ming_cursor)
        return odm_cursor

    @classmethod
    def get_model_class_by_collection(cls, cname):
        return cls._model_by_collection_name[cname]

def GqlQuery(stmt, *args, **kwargs):
    parse_result, cursor = gql.gql_statement_with_context(
        M.project_orm_session.db, stmt, *args, **kwargs)
    parse_result.pop('fields')
    cls = Model.get_model_class_by_collection(
        parse_result.pop('collection'))
    return ModelQuery(cls, **parse_result)
    
class ModelQuery(object):
    
    def __init__(self, cls,
                 filters=None,
                 spec=None,
                 sort=None,
                 limit=None,
                 skip=None):
        if filters is None: filters = []
        if spec is None: spec = {}
        self._cls = cls
        self._filters = filters
        self._spec = spec
        self._sort = sort
        self._limit = limit
        self._skip = skip

    def __len__(self):
        return self._build_cursor().count()

    def _clone(self, **kwargs):
        d = dict(
            filters=self._filters,
            spec=self._spec,
            sort=self._sort,
            limit=self._limit,
            skip=self._skip)
        d.update(kwargs)
        return ModelQuery(self._cls, **d)

    def filter(self, *args, **kwargs):
        return self._clone(filters=self._filters + [(args, kwargs)])

    def fetch(self, limit, offset=0):
        return self._clone(limit=limit, skip=offset)

    def _build_spec(self):
        spec = {}
        for f_args, f_kwargs in self._filters:
            if f_kwargs:
                spec.update(f_kwargs)
            else:
                prop_op, value = f_args
                prop, op = prop_op.strip().split(' ', 1)
                if op != '=':
                    import pdb; pdb.set_trace()
                spec[prop] = value
        spec.update(self._spec)
        return spec

    def _build_cursor(self):
        spec = self._build_spec()
        cursor = self._cls.query.find(spec)
        if self._sort:
            cursor = cursor.sort(self._sort)
        if self._limit:
            cursor = cursor.limit(self._limit)
        if self._skip:
            cursor = cursor.skip(self._skip)
        return cursor

    def __iter__(self):
        return iter(self._build_cursor())

class UserProperty(ming.odm.FieldProperty):

    def __init__(self, auto_current_user_add=False, **kwargs):
        if auto_current_user_add:
            kwargs['if_missing'] = lambda: users.get_current_user().username
        super(UserProperty, self).__init__(str, **kwargs)
