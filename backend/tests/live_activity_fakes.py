"""Async Motor stand-ins shared by the Live Activity tests (no dependency added).

Every collection call yields to the event loop once and then applies atomically, so
``asyncio.gather`` interleaves concurrent sweeps between calls, which is the granularity
MongoDB's single-document atomicity gives.
``FakeDB`` creates collections on first access and logs every call in ``db.log``
as ``(collection, method, args)`` so tests can spy on which collections were touched.
"""

import asyncio
import copy

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

WRITE_METHODS = {
    "insert_one", "insert_many", "update_one", "update_many", "replace_one",
    "delete_one", "delete_many", "find_one_and_update", "find_one_and_replace",
    "find_one_and_delete", "bulk_write", "create_index",
}


def _match(doc, flt):
    for k, v in flt.items():
        if isinstance(v, dict):
            for op, arg in v.items():
                if op == "$in" and doc.get(k) not in arg:
                    return False
                if op == "$exists" and (k in doc) != arg:
                    return False
                if op == "$lt" and not (k in doc and doc[k] < arg):
                    return False
                if op == "$gt" and not (k in doc and doc[k] > arg):
                    return False
        elif doc.get(k) != v:
            return False
    return True


def _project(doc, projection):
    doc = copy.deepcopy(doc)
    if not projection:
        return doc
    include = {k for k, v in projection.items() if v and k != "_id"}
    if include:
        return {k: v for k, v in doc.items() if k in include}
    return {k: v for k, v in doc.items() if k not in projection}


class _Cursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, key, direction=1):
        self._docs.sort(key=lambda d: d.get(key), reverse=direction < 0)
        return self

    async def to_list(self, _length):
        await asyncio.sleep(0)
        return list(self._docs)

    def __aiter__(self):
        async def gen():
            for d in self._docs:
                yield d

        return gen()


class _Result:
    def __init__(self, n):
        self.matched_count = n
        self.modified_count = n
        self.deleted_count = n


class FakeCollection:
    def __init__(self, name="", log=None):
        self.name = name
        self.log = log if log is not None else []
        self.docs = []
        self.unique = []

    def _note(self, method, *args):
        self.log.append((self.name, method, args))

    async def create_index(self, keys, unique=False, **_kw):
        await asyncio.sleep(0)
        self._note("create_index", keys)
        if unique:
            self.unique.append([k if isinstance(k, str) else k[0] for k in keys] if isinstance(keys, list) else [keys])
        return "idx"

    def _check_unique(self, doc):
        for fields in self.unique:
            for other in self.docs:
                if all(other.get(f) == doc.get(f) for f in fields):
                    raise DuplicateKeyError("duplicate key")

    @staticmethod
    def _apply(doc, update):
        for k, v in update.get("$set", {}).items():
            doc[k] = v
        for k in update.get("$unset", {}):
            doc.pop(k, None)
        for k, v in update.get("$inc", {}).items():
            doc[k] = doc.get(k, 0) + v
        for k, v in update.get("$push", {}).items():
            doc.setdefault(k, []).append(v)
        for k, cond in update.get("$pull", {}).items():
            lt = cond["$lt"]
            doc[k] = [x for x in doc.get(k, []) if not x < lt]

    def _insert_from(self, flt, update):
        doc = {k: v for k, v in flt.items() if not isinstance(v, dict)}
        doc.update(update.get("$setOnInsert", {}))
        self._apply(doc, update)
        self._check_unique(doc)
        self.docs.append(doc)
        return doc

    async def insert_one(self, doc):
        await asyncio.sleep(0)
        self._note("insert_one", doc)
        doc = copy.deepcopy(doc)
        self._check_unique(doc)
        self.docs.append(doc)
        return _Result(1)

    async def find_one(self, flt, projection=None):
        await asyncio.sleep(0)
        self._note("find_one", flt, projection)
        for d in self.docs:
            if _match(d, flt):
                return _project(d, projection)
        return None

    def find(self, flt=None, projection=None):
        self._note("find", flt, projection)
        return _Cursor([_project(d, projection) for d in self.docs if _match(d, flt or {})])

    async def find_one_and_update(self, flt, update, upsert=False, return_document=ReturnDocument.BEFORE):
        await asyncio.sleep(0)
        self._note("find_one_and_update", flt, update)
        for d in self.docs:
            if _match(d, flt):
                before = copy.deepcopy(d)
                self._apply(d, update)
                return copy.deepcopy(d) if return_document == ReturnDocument.AFTER else before
        if upsert:
            doc = self._insert_from(flt, update)
            return copy.deepcopy(doc) if return_document == ReturnDocument.AFTER else None
        return None

    async def update_one(self, flt, update, upsert=False):
        await asyncio.sleep(0)
        self._note("update_one", flt, update)
        for d in self.docs:
            if _match(d, flt):
                self._apply(d, update)
                return _Result(1)
        if upsert:
            self._insert_from(flt, update)
        return _Result(0)

    async def update_many(self, flt, update):
        await asyncio.sleep(0)
        self._note("update_many", flt, update)
        n = 0
        for d in self.docs:
            if _match(d, flt):
                self._apply(d, update)
                n += 1
        return _Result(n)


    async def delete_one(self, flt):
        await asyncio.sleep(0)
        self._note("delete_one", flt)
        for i, d in enumerate(self.docs):
            if _match(d, flt):
                del self.docs[i]
                return _Result(1)
        return _Result(0)

    async def delete_many(self, flt):
        await asyncio.sleep(0)
        self._note("delete_many", flt)
        keep = [d for d in self.docs if not _match(d, flt)]
        n = len(self.docs) - len(keep)
        self.docs[:] = keep
        return _Result(n)


class FakeDB:
    """Collections appear on first attribute access; every call is logged in ``log``."""

    def __init__(self):
        self.log = []
        self._collections = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name not in self._collections:
            self._collections[name] = FakeCollection(name, self.log)
        return self._collections[name]


class FakeRedis:
    def __init__(self):
        self.keys = {}

    async def set(self, key, value, nx=False, ex=None):
        if nx and key in self.keys:
            return None
        self.keys[key] = value
        return True


class CountingRedis:
    """INCR/EXPIRE subset used by the widget rate limit."""

    def __init__(self):
        self.counts = {}
        self.expiries = {}

    async def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    async def expire(self, key, seconds):
        self.expiries[key] = seconds
        return True


class DownRedis:
    async def set(self, *_a, **_kw):
        raise ConnectionError("redis down")

    async def incr(self, *_a, **_kw):
        raise ConnectionError("redis down")
