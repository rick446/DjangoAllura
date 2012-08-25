from pylons import c
from allura import model as M

import bson
import ming
from ming import gql
from ming import schema as S
from ming.declarative import Document

from . import users

Blob = bson.Binary

def run_in_transaction(func, *args, **kwargs):
    '''Not really; we use MongoDB'''
    return func(*args, **kwargs)

def put(models):
    for model in models:
        model.put()

def idgen(cls, kind):
    def gen_id():
        db = cls.__mongometa__.session.db
        doc = db._identifier.find_and_modify(
            {'_id': kind},
            {'$inc': { 'next_id': 1 } },
            upsert=True, new=True)
        return doc['next_id']
    return gen_id

class KeyIdentifierSchema(S.Scalar):

    def __init__(self, **kw):
        self.int = S.Int(**kw)
        self.str = S.String(**kw)
        self.missing = lambda:None
        super(KeyIdentifierSchema, self).__init__(if_missing=lambda:self.missing(), **kw)

    def _validate(self, value, **kw):
        try:
            result = self.int._validate(value, **kw)
        except S.Invalid:
            result = self.str._validate(value, **kw)
        return result

class KeyType(ming.base.Object):

    def id(self):
        return self.identifier

class KeyTypeSchema(S.Object):

    def __init__(self, **kw):
        fields = dict(
            kind=S.Value(None), # will be filled in later
            identifier=KeyIdentifierSchema(),
            ancestor_path=[
                dict(kind=str,
                     identifier=KeyIdentifierSchema()) ])
        super(KeyTypeSchema, self).__init__(fields=fields, **kw)

    def _validate(self, value, **kw):
        result = super(KeyType, self)._validate(value, **kw)
        return KeyType(result)

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

class _ModelMeta(Document.__metaclass__):

    def __new__(meta, name, bases, dct):
        mm = dct.get('__mongometa__')
        if not mm:
            class __mongometa__: pass
            dct['__mongometa__'] = mm = __mongometa__
        dct['_id'] = ming.Field(KeyTypeSchema)
        mm.name = name
        cls = Document.__metaclass__.__new__(meta, name, bases, dct)
        cls._model_by_collection_name[name] = cls
        cls._meta = _DjangoMeta(cls)
        cls._id.field.schema.fields['kind'].value = name
        cls._id.field.schema.fields['kind'].if_missing = name
        cls._id.field.schema.fields['identifier'].missing = idgen(cls, name)
        return cls

class _DjangoMeta(object):

    def __init__(self, cls):
        self._cls = cls

    @property
    def fields(self):
        return []

    @property
    def many_to_many(self):
        return []

class Model(Document):
    __metaclass__ = _ModelMeta
    _model_by_collection_name = {}
    class __mongometa__:
        session = M.project_doc_session

    class DoesNotExist(Exception): pass

    def __init__(self, **kwargs):
        super(Model, self).__init__(kwargs)

    def key(self):
        return self._id

    def put(self):
        self.m.save()

    @classmethod
    def all(cls):
        return ModelQuery(cls)

    @classmethod
    def gae_get(cls, key_or_keys):
        if isinstance(key_or_keys, (list, set)):
            return cls.m.find(dict(
                    _id={'$in': list(key_or_keys)})).all()
        else:
            return cls.m.get(_id=key_or_keys)

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
                kwds = {'_id': str(key)}
                if parent is not None:
                    kwds['gae_ancestry__icontains'] = str(parent.key())
                result.append(cls.m.get(**kwds))
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
            cls.m.mapper.collection.m.collection,
            gql_text, *args, **kwargs)
        return pymongo_cursor

    @classmethod
    def get_model_class_by_collection(cls, cname):
        return cls._model_by_collection_name[cname]

class GqlQuery(object):

    def __init__(self, stmt, *args, **kwargs):
        self._stmt = stmt
        self._args = args
        self._kwargs = kwargs
        self._model_query = None

    def bind(self, *args, **kwargs):
        return GqlQuery(self._stmt, *args, **kwargs)

    def _do_query(self):
        parse_result, cursor = gql.gql_statement_with_context(
            M.project_orm_session.db, self._stmt, *self._args, **self._kwargs)
        parse_result.pop('fields')
        cls = Model.get_model_class_by_collection(
            parse_result.pop('collection'))
        return ModelQuery(cls, **parse_result)

    def __iter__(self):
        return iter(self._do_query())

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
        cursor = self._cls.m.find(spec)
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
            kwargs['if_missing'] = self._current_user_username
            kwargs['required'] = False
        super(UserProperty, self).__init__(str, **kwargs)

    def _current_user_username(self):
        u = users.get_current_user()
        if u: return u.username
        return None
        

