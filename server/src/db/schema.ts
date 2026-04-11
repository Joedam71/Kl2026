import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

const DATA_DIR = path.resolve(__dirname, '../../../data');
const DB_PATH = path.join(DATA_DIR, 'kl2026.db');

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    if (!fs.existsSync(DATA_DIR)) {
      fs.mkdirSync(DATA_DIR, { recursive: true });
    }
    _db = new Database(DB_PATH);
    _db.pragma('journal_mode = WAL');
    _db.pragma('foreign_keys = ON');
  }
  return _db;
}

export function initDb(): void {
  const db = getDb();

  db.exec(`
    CREATE TABLE IF NOT EXISTS media (
      id            INTEGER PRIMARY KEY AUTOINCREMENT,
      file_path     TEXT    NOT NULL UNIQUE,
      type          TEXT    NOT NULL DEFAULT 'movie',
      title         TEXT    NOT NULL,
      year          INTEGER,
      tmdb_id       INTEGER,
      overview      TEXT,
      poster_path   TEXT,
      backdrop_path TEXT,
      genres        TEXT,
      rating        REAL,
      runtime       INTEGER,
      season        INTEGER,
      episode       INTEGER,
      added_at      INTEGER NOT NULL DEFAULT (unixepoch()),
      last_scanned  INTEGER NOT NULL DEFAULT (unixepoch())
    );

    CREATE TABLE IF NOT EXISTS progress (
      id               INTEGER PRIMARY KEY AUTOINCREMENT,
      media_id         INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
      position_seconds REAL    NOT NULL DEFAULT 0,
      duration_seconds REAL    NOT NULL DEFAULT 0,
      updated_at       INTEGER NOT NULL DEFAULT (unixepoch()),
      UNIQUE(media_id)
    );

    CREATE TABLE IF NOT EXISTS settings (
      key   TEXT PRIMARY KEY,
      value TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_media_type    ON media(type);
    CREATE INDEX IF NOT EXISTS idx_media_title   ON media(title);
    CREATE INDEX IF NOT EXISTS idx_media_year    ON media(year);
    CREATE INDEX IF NOT EXISTS idx_progress_upd  ON progress(updated_at DESC);
  `);

  // Default settings
  const hasDirs = db.prepare("SELECT 1 FROM settings WHERE key = 'media_dirs'").get();
  if (!hasDirs) {
    db.prepare("INSERT INTO settings (key, value) VALUES ('media_dirs', '[]')").run();
  }
  const hasKey = db.prepare("SELECT 1 FROM settings WHERE key = 'tmdb_api_key'").get();
  if (!hasKey) {
    db.prepare("INSERT INTO settings (key, value) VALUES ('tmdb_api_key', ?)").run(
      process.env.TMDB_API_KEY || ''
    );
  }
  const hasBase = db.prepare("SELECT 1 FROM settings WHERE key = 'tmdb_image_base'").get();
  if (!hasBase) {
    db.prepare("INSERT INTO settings (key, value) VALUES ('tmdb_image_base', 'https://image.tmdb.org/t/p')").run();
  }

  console.log('Database ready:', DB_PATH);
}
