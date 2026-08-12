"""
dbshim.py — a tiny SQLite-call-compatible layer backed by MongoDB.

PiCodeHub's app.py talks to the DB with plain, simple SQL:
    conn = get_db()
    conn.execute("SELECT * FROM table WHERE col = ?", (val,)).fetchone()
    conn.execute("INSERT INTO table (a, b) VALUES (?, ?)", (1, 2))
    conn.commit()
    conn.close()

Every query in this project is a single-table SELECT / INSERT / UPDATE /
DELETE (only one JOIN exists anywhere, and that call site is handled
separately, directly in app.py, using get_raw_db()).

Rather than hand-rewrite ~30 route handlers, this module parses that
narrow subset of SQL and executes the equivalent operation against
MongoDB — so app.py and auth.py keep working almost unchanged, while the
actual storage engine underneath is MongoDB Atlas.

Auto-increment integer ids are preserved (app.py's routes use
<int:id> in URLs) via a "counters" collection, so every document still
has a plain integer "id" field alongside Mongo's own "_id".
"""

import os
import re
from datetime import datetime, timezone

from pymongo import MongoClient

_client = None
_db = None


def _now():
    return datetime.now(timezone.utc).isoformat()


def get_raw_db():
    """Return the underlying pymongo Database, for the rare query this
    shim doesn't cover (e.g. the one admin JOIN in app.py)."""
    global _client, _db
    if _db is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError(
                "MONGODB_URI is not set. Add it to your .env / Render "
                "environment variables (see DEPLOYMENT.md)."
            )
        _client = MongoClient(uri)
        dbname = os.environ.get("MONGODB_DB", "picodehub")
        _db = _client[dbname]
    return _db


def _next_id(table):
    db = get_raw_db()
    doc = db.counters.find_one_and_update(
        {"_id": table},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return doc["seq"]


class Row(dict):
    """Behaves like sqlite3.Row: row["col"] and dict(row) both work."""
    pass


class Cursor:
    def __init__(self, rows=None, lastrowid=None):
        self._rows = rows or []
        self.lastrowid = lastrowid

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


_AUTO_TIMESTAMP_FIELDS = {"created_at", "purchased_at", "updated_at"}


def _parse_literal(token):
    token = token.strip()
    if token == "?":
        return "__PARAM__"
    if token.upper() == "CURRENT_TIMESTAMP":
        return _now()
    if (token.startswith("'") and token.endswith("'")) or (token.startswith('"') and token.endswith('"')):
        return token[1:-1]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    return token


def _split_top_level(s, sep=","):
    # No nested parens/quotes-with-commas occur in this project's SQL,
    # so a plain split is safe.
    return [p.strip() for p in s.split(sep)]


def _consume(tokens, params_iter):
    """Given a list of raw literal/placeholder tokens (already split),
    resolve each '?' against the next value from params_iter."""
    out = []
    for t in tokens:
        v = _parse_literal(t)
        if v == "__PARAM__":
            out.append(next(params_iter))
        else:
            out.append(v)
    return out


def _parse_where(where_sql, params_iter):
    """'col = ? AND col2 = 1' -> {'col': val, 'col2': 1}"""
    if not where_sql:
        return {}
    if re.search(r"\bOR\b", where_sql, flags=re.IGNORECASE):
        raise NotImplementedError(
            "dbshim's SQL-subset parser does not support OR in WHERE clauses: "
            f"{where_sql!r}. Split this into two separate queries in app.py instead."
        )
    conds = re.split(r"\s+AND\s+", where_sql.strip(), flags=re.IGNORECASE)
    query = {}
    for c in conds:
        m = re.match(r"([\w.]+)\s*=\s*(.+)", c.strip())
        if not m:
            continue
        col, val_token = m.group(1), m.group(2).strip()
        val = _parse_literal(val_token)
        if val == "__PARAM__":
            val = next(params_iter)
        query[col] = val
    return query


_SELECT_RE = re.compile(
    r"^SELECT\s+(.+?)\s+FROM\s+(\w+)"
    r"(?:\s+WHERE\s+(.+?))?"
    r"(?:\s+ORDER\s+BY\s+([\w.]+)(\s+ASC|\s+DESC)?)?"
    r"(?:\s+LIMIT\s+(\d+))?$",
    re.IGNORECASE,
)
_INSERT_RE = re.compile(
    r"^INSERT\s+INTO\s+(\w+)\s*\((.+?)\)\s*VALUES\s*\((.+?)\)$", re.IGNORECASE
)
_UPDATE_RE = re.compile(
    r"^UPDATE\s+(\w+)\s+SET\s+(.+?)\s+WHERE\s+(.+)$", re.IGNORECASE
)
_DELETE_RE = re.compile(r"^DELETE\s+FROM\s+(\w+)\s+WHERE\s+(.+)$", re.IGNORECASE)


class Connection:
    def execute(self, sql, params=()):
        norm = re.sub(r"\s+", " ", sql.strip())
        upper = norm.upper()
        params_iter = iter(params)

        if upper.startswith("CREATE TABLE") or upper.startswith("PRAGMA"):
            return Cursor()  # schemaless — nothing to do

        m = _SELECT_RE.match(norm)
        if m:
            cols_raw, table, where_sql, order_col, order_dir, limit = m.groups()
            query = _parse_where(where_sql, params_iter)
            db = get_raw_db()
            cursor = db[table].find(query, {"_id": 0})
            if order_col:
                order_col = order_col.split(".")[-1]
                direction = -1 if (order_dir and "DESC" in order_dir.upper()) else 1
                cursor = cursor.sort(order_col, direction)
            if limit:
                cursor = cursor.limit(int(limit))
            docs = [Row(d) for d in cursor]
            if cols_raw.strip() != "*" and "cr.*" not in cols_raw:
                wanted = [c.strip().split(".")[-1] for c in cols_raw.split(",")]
                docs = [Row({k: d.get(k) for k in wanted}) for d in docs]
            return Cursor(rows=docs)

        m = _INSERT_RE.match(norm)
        if m:
            table, cols_raw, vals_raw = m.groups()
            cols = _split_top_level(cols_raw)
            val_tokens = _split_top_level(vals_raw)
            values = _consume(val_tokens, params_iter)
            doc = dict(zip(cols, values))
            new_id = _next_id(table)
            doc["id"] = new_id
            for f in _AUTO_TIMESTAMP_FIELDS:
                if f not in doc:
                    doc[f] = _now()
            if table == "users" and "is_admin" not in doc:
                doc["is_admin"] = 0
            get_raw_db()[table].insert_one(doc)
            return Cursor(lastrowid=new_id)

        m = _UPDATE_RE.match(norm)
        if m:
            table, set_sql, where_sql = m.groups()
            set_parts = _split_top_level(set_sql)
            update = {}
            for part in set_parts:
                col, val_token = part.split("=", 1)
                col = col.strip()
                val = _parse_literal(val_token.strip())
                if val == "__PARAM__":
                    val = next(params_iter)
                update[col] = val
            query = _parse_where(where_sql, params_iter)
            get_raw_db()[table].update_many(query, {"$set": update})
            return Cursor()

        m = _DELETE_RE.match(norm)
        if m:
            table, where_sql = m.groups()
            query = _parse_where(where_sql, params_iter)
            get_raw_db()[table].delete_many(query)
            return Cursor()

        raise NotImplementedError(f"dbshim cannot parse this query: {sql}")

    def commit(self):
        pass  # every op above already wrote straight to Mongo

    def close(self):
        pass  # shared client stays open; nothing per-connection to close


def get_db():
    return Connection()
