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

class KeyIdSchema(S.Scalar):

    def __init__(self, **kw):
        self.int = S.Int(**kw)
        self.str = S.String(**kw)
        self.missing = lambda:None
        super(KeyIdSchema, self).__init__(if_missing=lambda:self.missing(), **kw)

    def _validate(self, value, **kw):
        try:
            result = self.int._validate(value, **kw)
        except S.Invalid:
            result = self.str._validate(value, **kw)
        return result

class Key(ming.base.Object):

    def __init__(self, **kwargs):
        super(Key, self).__init__(kwargs)

    def id(self):
        return self.s.id

    def as_path(self):
        return [ self.s ] + self.p

class KeySchema(S.Object):

    def __init__(self, **kw):
        fields = dict(
            s=dict(kind=S.Value(None), id=KeyIdSchema()),
            p=[ dict(kind=str, id=KeyIdSchema()) ])
        super(KeySchema, self).__init__(fields=fields, **kw)

    def _validate(self, value, **kw):
        result = super(KeySchema, self)._validate(value, **kw)
        return Key(**result)

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
        dct['_id'] = ming.Field(KeySchema)
        mm.name = name
        cls = Document.__metaclass__.__new__(meta, name, bases, dct)
        cls._model_by_collection_name[name] = cls
        cls._meta = _DjangoMeta(cls)
        s = cls._id.field.schema.fields['s'].fields
        s['kind'].value = s['kind'].if_missing = name
        s['id'].missing = idgen(cls, name)
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
        if '_id' in kwargs:
            assert isinstance(kwargs['_id'], Key)
            assert 'parent' not in kwargs
            assert 'key_name' not in kwargs
        else:
            parent = kwargs.pop('parent', None)
            if isinstance(parent, Model):
                parent = parent._id
            s_id = kwargs.pop('key_name', None)
            if s_id is None:
                s_id = idgen(self, self.kind())()
            key = Key(
                s=ming.base.Object(
                    id=s_id, kind=self.kind()),
                p=parent.as_path() if parent else [])
            kwargs['_id'] = key
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
            key_ss = [ k.s for k in key_or_keys ]
            q = { '_id.s': { '$in': key_ss } }
            results = dict(
                (obj._id.s, obj) for obj in cls.m.find(q))
            return [ results.get(key_s, None)
                     for key_s in key_ss ]
        else:
            q = {'_id.s': key_or_keys.s } 
            return cls.m.find(q).first()

    @classmethod
    def get_or_insert(cls, key_name, **kwargs):
        parent = kwargs.get('parent', None)
        if parent:
            p = parent.as_path()
        else:
            p = []
        key = Key(s=dict(kind=cls.kind(), id=key_name), p=p)
        result = cls.gae_get(key)
        if result is None:
            result = cls(_id=key, **kwargs)
            result.put()
        return result

    @classmethod
    def kind(cls):
        return cls.__name__

    @classmethod
    def get_by_key_name(cls, key_names, parent=None):
        q = {}
        if parent:
            if isinstance(parent, Model):
                parent = parent._id
            q['_id.p.0.s'] = parent.s
        if isinstance(key_names, (list, set)):
            q['_id.s.id'] = { '$in': key_names } 
            results = dict(
                (obj._id.s, obj) for obj in cls.m.find(q))
            return [ results.get(key_name, None)
                     for key_name in key_names ]
        else:
            q['_id.s.id'] = key_names
            return cls.m.find(q).first()

    get_by_id = get_by_key_name

    @classmethod
    def gql(cls, gql_text, *args, **kwargs):
        pymongo_cursor = gql.gql_filter(
            cls.m.collection,
            gql_text, *args, **kwargs)
        return ming.Cursor(cls, pymongo_cursor, allow_extra=True, strip_extra=True)

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

    def order(self, name):
        return self._clone(sort=name)

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

class UserProperty(ming.Field):

    def __init__(self, auto_current_user_add=False, **kwargs):
        if auto_current_user_add:
            kwargs['if_missing'] = self._current_user_username
            kwargs['required'] = False
        super(UserProperty, self).__init__(str, **kwargs)

    def _current_user_username(self):
        u = users.get_current_user()
        if u: return u.username
        return None
        
class ReferenceProperty(ming.Field):

    def __init__(self, cls):
        super(ReferenceProperty, self).__init__(KeySchema)
        s = self.schema.fields['s'].fields
        s['kind'].value = s['kind'].if_missing = cls.kind()
        self._cls = cls

