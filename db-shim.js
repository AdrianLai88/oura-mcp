'use strict';

// Drop-in replacement for better-sqlite3 using JSON-file persistence.
// Implements only the API patterns used by auth-server.js.

const fs = require('fs');

function loadData(dbPath) {
  try {
    return JSON.parse(fs.readFileSync(dbPath, 'utf8'));
  } catch {
    return {};
  }
}

function saveData(dbPath, tables) {
  const tmp = dbPath + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(tables));
  fs.renameSync(tmp, dbPath);
}

// Parse "col op ?" or "col op 'literal'" conditions joined by AND.
function parseWhere(where, params) {
  const parts = where.split(/\s+AND\s+/i);
  let pi = 0;
  return parts.map(part => {
    const t = part.trim();
    const qm = t.match(/^(\w+)\s*([<>=!]+)\s*\?$/);
    if (qm) return { col: qm[1], op: qm[2], val: params[pi++] };
    const lit = t.match(/^(\w+)\s*([<>=!]+)\s*'([^']*)'$/);
    if (lit) return { col: lit[1], op: lit[2], val: lit[3] };
    throw new Error(`Unsupported WHERE clause: ${part}`);
  });
}

function matchRow(row, conds) {
  return conds.every(({ col, op, val }) => {
    const v = row[col];
    if (op === '=' || op === '==') return v == val;  // eslint-disable-line eqeqeq
    if (op === '<') return v < val;
    if (op === '>') return v > val;
    if (op === '<=') return v <= val;
    if (op === '!=') return v != val;  // eslint-disable-line eqeqeq
    return false;
  });
}

class Statement {
  constructor(sql, tables, dbPath) {
    this._sql = sql.trim();
    this._tables = tables;
    this._dbPath = dbPath;
  }

  run(...args) {
    const params = args.flat();
    const sql = this._sql;

    const del = sql.match(/^DELETE FROM (\w+) WHERE (.+)$/i);
    if (del) {
      const t = this._tables[del[1]];
      if (t) {
        const conds = parseWhere(del[2], params);
        for (const key of Object.keys(t)) {
          if (matchRow(t[key], conds)) delete t[key];
        }
        saveData(this._dbPath, this._tables);
      }
      return;
    }

    const ins = sql.match(/^INSERT INTO (\w+) \(([^)]+)\) VALUES \(([^)]+)\)$/i);
    if (ins) {
      const cols = ins[2].split(',').map(s => s.trim());
      const t = this._tables[ins[1]];
      if (t) {
        const row = {};
        cols.forEach((col, i) => { row[col] = params[i] !== undefined ? params[i] : null; });
        t[String(row[cols[0]])] = row;
        saveData(this._dbPath, this._tables);
      }
      return;
    }

    throw new Error(`Unsupported SQL in run(): ${sql}`);
  }

  get(...args) {
    const params = args.flat();
    const sql = this._sql;

    const sel = sql.match(/^SELECT \* FROM (\w+) WHERE (.+)$/i);
    if (sel) {
      const t = this._tables[sel[1]];
      if (!t) return undefined;
      const conds = parseWhere(sel[2], params);
      for (const row of Object.values(t)) {
        if (matchRow(row, conds)) return row;
      }
      return undefined;
    }

    throw new Error(`Unsupported SQL in get(): ${sql}`);
  }

  all(...args) {
    const params = args.flat();
    const sql = this._sql;

    const sel = sql.match(/^SELECT \* FROM (\w+) WHERE (.+)$/i);
    if (sel) {
      const t = this._tables[sel[1]];
      if (!t) return [];
      const conds = parseWhere(sel[2], params);
      return Object.values(t).filter(row => matchRow(row, conds));
    }

    throw new Error(`Unsupported SQL in all(): ${sql}`);
  }
}

class Database {
  constructor(dbPath) {
    this._dbPath = dbPath;
    this._tables = loadData(dbPath);
  }

  pragma() { /* no-op — WAL mode only matters for concurrent writers */ }

  exec(sql) {
    let m;
    const re = /CREATE TABLE IF NOT EXISTS (\w+)\s*\([^)]+\)/gi;
    while ((m = re.exec(sql)) !== null) {
      if (!this._tables[m[1]]) this._tables[m[1]] = {};
    }
    saveData(this._dbPath, this._tables);
  }

  prepare(sql) {
    return new Statement(sql, this._tables, this._dbPath);
  }
}

module.exports = Database;
