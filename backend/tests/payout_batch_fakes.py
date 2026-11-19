"""In-memory async Mongo fake for payout batch concurrency tests.

Models what the batch code relies on:
- filters: equality (None matches missing), $in, $nin, $exists, $lt, $ne, $or;
- update_one / update_many apply the filter and the update atomically (no await
  between match and write), so conditional updates race like they do in Mongo;
- every operation yields to the event loop first, so concurrent tasks interleave;
- create_index(unique=True, partialFilterExpression=...) is enforced on insert_one
  (pymongo DuplicateKeyError) and validated against existing docs at build time.
"""
import asyncio
import copy
from types import SimpleNamespace

from pymongo.errors import DuplicateKeyError, OperationFailure

_MISSING = object()


def _eq(val, want):
    if want is None:
        return val is _MISSING or val is None
    if val is _MISSING:
        return False
    if isinstance(val, list) and not isinstance(want, list):
        return want in val
    return val == want


def _in(val, options):
    if val is _MISSING:
        return None in options
    if isinstance(val, list):
        return any(v in options for v in val)
    return val in options


def _match_value(val, cond):
    if isinstance(cond, dict) and cond and all(k.startswith("$") for k in cond):
        for op, arg in cond.items():
            if op == "$in":
                ok = _in(val, arg)
            elif op == "$nin":
                ok = not _in(val, arg)
            elif op == "$exists":
                ok = (val is not _MISSING) == bool(arg)
            elif op == "$lt":
                ok = val is not _MISSING and val is not None and val < arg
            elif op == "$ne":
                ok = not _eq(val, arg)
            else:
                raise NotImplementedError(op)
            if not ok:
                return False
        return True
    return _eq(val, cond)


def matches(doc, flt):
    for key, cond in (flt or {}).items():
        if key == "$or":
            if not any(matches(doc, f) for f in cond):
                return False
            continue
        if not _match_value(doc.get(key, _MISSING), cond):
            return False
    return True


def _apply(doc, update):
    for op, fields in update.items():
        for k, v in fields.items():
            if op == "$set":
                doc[k] = copy.deepcopy(v)
            elif op == "$unset":
                doc.pop(k, None)
            elif op == "$inc":
                doc[k] = doc.get(k, 0) + v
            elif op == "$push":
                doc.setdefault(k, []).append(copy.deepcopy(v))
            else:
                raise NotImplementedError(op)


class FakeCursor:
    def __init__(self, coll, flt):
        self._coll = coll
        self._flt = flt
        self._sort = None
        self._limit = 0

    def sort(self, key, direction=1):
        self._sort = (key, direction)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _snapshot(self):
        docs = [copy.deepcopy(d) for d in self._coll.docs if matches(d, self._flt)]
        if self._sort:
            key, direction = self._sort
            docs.sort(key=lambda d: d.get(key) or "", reverse=direction < 0)
        if self._limit:
            docs = docs[: self._limit]
        return docs

    async def __aiter__(self):
        await asyncio.sleep(0)
        for doc in self._snapshot():
            yield doc
            await asyncio.sleep(0)

    async def to_list(self, n=None):
        await asyncio.sleep(0)
        docs = self._snapshot()
        return docs[:n] if n else docs


class FakeCollection:
    def __init__(self, name):
        self.name = name
        self.docs = []
        self.indexes = {}  # name -> {"key": [...], "unique": bool, "partialFilterExpression": {...}}
        self.after_update = []  # async hooks(flt, update) run after a successful update_one

    # -- indexes ---------------------------------------------------------
    def _unique_violations(self, doc, idx, docs):
        field = idx["key"][0][0]
        partial = idx.get("partialFilterExpression")
        if partial is not None and not matches(doc, partial):
            return False
        for other in docs:
            if other is doc:
                continue
            if partial is not None and not matches(other, partial):
                continue
            if other.get(field, _MISSING) == doc.get(field, _MISSING):
                return True
        return False

    async def create_index(self, keys, **kw):
        await asyncio.sleep(0)
        keys = [(keys, 1)] if isinstance(keys, str) else list(keys)
        name = kw.get("name") or "_".join(f"{k}_{d}" for k, d in keys)
        spec = {"key": keys, "unique": bool(kw.get("unique"))}
        if kw.get("partialFilterExpression") is not None:
            spec["partialFilterExpression"] = kw["partialFilterExpression"]
        if kw.get("sparse"):
            spec["sparse"] = True
        existing = self.indexes.get(name)
        if existing is not None:
            if existing != spec:
                raise OperationFailure(f"Index with name: {name} already exists with different options", code=85)
            return name
        if spec["unique"]:
            for doc in self.docs:
                if self._unique_violations(doc, spec, self.docs):
                    raise DuplicateKeyError(f"E11000 duplicate key error collection: {self.name} index: {name}")
        self.indexes[name] = spec
        return name

    async def index_information(self):
        await asyncio.sleep(0)
        return copy.deepcopy(self.indexes)

    async def drop_index(self, name):
        await asyncio.sleep(0)
        if name not in self.indexes:
            raise OperationFailure(f"index not found with name [{name}]", code=27)
        del self.indexes[name]

    # -- reads -------------------------------------------------------------
    def find(self, flt=None, projection=None):
        return FakeCursor(self, flt or {})

    async def find_one(self, flt=None, projection=None, sort=None):
        await asyncio.sleep(0)
        docs = [d for d in self.docs if matches(d, flt or {})]
        if sort:
            key, direction = sort[0]
            docs.sort(key=lambda d: d.get(key) or "", reverse=direction < 0)
        return copy.deepcopy(docs[0]) if docs else None

    async def count_documents(self, flt):
        await asyncio.sleep(0)
        return sum(1 for d in self.docs if matches(d, flt))

    # -- writes ------------------------------------------------------------
    async def insert_one(self, doc):
        await asyncio.sleep(0)
        new = copy.deepcopy(doc)
        for name, idx in self.indexes.items():
            if idx["unique"] and self._unique_violations(new, idx, self.docs):
                raise DuplicateKeyError(f"E11000 duplicate key error collection: {self.name} index: {name}")
        self.docs.append(new)
        return SimpleNamespace(inserted_id=doc.get("id"))

    async def update_one(self, flt, update, upsert=False):
        await asyncio.sleep(0)
        for doc in self.docs:
            if matches(doc, flt):
                _apply(doc, update)
                for hook in list(self.after_update):
                    await hook(flt, update)
                return SimpleNamespace(matched_count=1, modified_count=1)
        return SimpleNamespace(matched_count=0, modified_count=0)

    async def update_many(self, flt, update):
        await asyncio.sleep(0)
        n = 0
        for doc in self.docs:
            if matches(doc, flt):
                _apply(doc, update)
                n += 1
        return SimpleNamespace(matched_count=n, modified_count=n)


class FakeDB:
    def __init__(self):
        self._colls = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    def __getitem__(self, name):
        if name not in self._colls:
            self._colls[name] = FakeCollection(name)
        return self._colls[name]
