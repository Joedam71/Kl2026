import { getDb } from './schema';
import type { Media, Progress } from '../types';

// ── Media ──────────────────────────────────────────────────────────────────

export function getAllMedia(filters?: { type?: string; genre?: string }): Media[] {
  const db = getDb();
  let sql = 'SELECT * FROM media WHERE 1=1';
  const params: (string | number)[] = [];

  if (filters?.type) {
    sql += ' AND type = ?';
    params.push(filters.type);
  }
  if (filters?.genre) {
    sql += ' AND genres LIKE ?';
    params.push(`%${filters.genre}%`);
  }

  sql += ' ORDER BY title ASC';
  return db.prepare(sql).all(...params) as Media[];
}

export function getMediaById(id: number): Media | undefined {
  return getDb().prepare('SELECT * FROM media WHERE id = ?').get(id) as Media | undefined;
}

export function getMediaByPath(filePath: string): Media | undefined {
  return getDb().prepare('SELECT * FROM media WHERE file_path = ?').get(filePath) as Media | undefined;
}

export function insertMedia(item: Omit<Media, 'id' | 'added_at' | 'last_scanned'>): number {
  const db = getDb();
  const result = db.prepare(`
    INSERT INTO media (file_path, type, title, year, tmdb_id, overview, poster_path,
      backdrop_path, genres, rating, runtime, season, episode)
    VALUES (@file_path, @type, @title, @year, @tmdb_id, @overview, @poster_path,
      @backdrop_path, @genres, @rating, @runtime, @season, @episode)
    ON CONFLICT(file_path) DO UPDATE SET last_scanned = unixepoch()
  `).run(item);
  return result.lastInsertRowid as number;
}

export function updateMediaMetadata(id: number, meta: Partial<Media>): void {
  const db = getDb();
  db.prepare(`
    UPDATE media SET
      title         = COALESCE(@title, title),
      tmdb_id       = COALESCE(@tmdb_id, tmdb_id),
      overview      = COALESCE(@overview, overview),
      poster_path   = COALESCE(@poster_path, poster_path),
      backdrop_path = COALESCE(@backdrop_path, backdrop_path),
      genres        = COALESCE(@genres, genres),
      rating        = COALESCE(@rating, rating),
      runtime       = COALESCE(@runtime, runtime),
      last_scanned  = unixepoch()
    WHERE id = @id
  `).run({ id, ...meta });
}

export function deleteMedia(id: number): void {
  getDb().prepare('DELETE FROM media WHERE id = ?').run(id);
}

export function searchMedia(query: string, type?: string): Media[] {
  const db = getDb();
  let sql = "SELECT * FROM media WHERE title LIKE ?";
  const params: (string | number)[] = [`%${query}%`];
  if (type) {
    sql += ' AND type = ?';
    params.push(type);
  }
  sql += ' ORDER BY title ASC LIMIT 50';
  return db.prepare(sql).all(...params) as Media[];
}

export function getGenres(): string[] {
  const rows = getDb().prepare('SELECT DISTINCT genres FROM media WHERE genres IS NOT NULL').all() as { genres: string }[];
  const set = new Set<string>();
  for (const row of rows) {
    try {
      const arr = JSON.parse(row.genres) as string[];
      arr.forEach(g => set.add(g));
    } catch {}
  }
  return [...set].sort();
}

export function getFeatured(): Media | undefined {
  const db = getDb();
  // Prefer items with backdrop + overview, pick a random one from top-rated
  const item = db.prepare(`
    SELECT * FROM media
    WHERE backdrop_path IS NOT NULL AND overview IS NOT NULL
    ORDER BY RANDOM() LIMIT 1
  `).get() as Media | undefined;
  return item ?? (db.prepare('SELECT * FROM media ORDER BY RANDOM() LIMIT 1').get() as Media | undefined);
}

// ── Progress ───────────────────────────────────────────────────────────────

export function getProgress(mediaId: number): Progress | undefined {
  return getDb().prepare('SELECT * FROM progress WHERE media_id = ?').get(mediaId) as Progress | undefined;
}

export function upsertProgress(mediaId: number, positionSeconds: number, durationSeconds: number): void {
  getDb().prepare(`
    INSERT INTO progress (media_id, position_seconds, duration_seconds, updated_at)
    VALUES (?, ?, ?, unixepoch())
    ON CONFLICT(media_id) DO UPDATE SET
      position_seconds = excluded.position_seconds,
      duration_seconds = excluded.duration_seconds,
      updated_at       = unixepoch()
  `).run(mediaId, positionSeconds, durationSeconds);
}

export function getContinueWatching(): (Media & { position_seconds: number; duration_seconds: number })[] {
  return getDb().prepare(`
    SELECT m.*, p.position_seconds, p.duration_seconds
    FROM progress p
    JOIN media m ON m.id = p.media_id
    WHERE p.duration_seconds > 0
      AND (p.position_seconds / p.duration_seconds) BETWEEN 0.02 AND 0.93
    ORDER BY p.updated_at DESC
    LIMIT 20
  `).all() as (Media & { position_seconds: number; duration_seconds: number })[];
}

// ── Settings ───────────────────────────────────────────────────────────────

export function getSetting(key: string): string | null {
  const row = getDb().prepare('SELECT value FROM settings WHERE key = ?').get(key) as { value: string } | undefined;
  return row?.value ?? null;
}

export function setSetting(key: string, value: string): void {
  getDb().prepare('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)').run(key, value);
}

export function getAllSettings(): Record<string, string> {
  const rows = getDb().prepare('SELECT key, value FROM settings').all() as { key: string; value: string }[];
  return Object.fromEntries(rows.map(r => [r.key, r.value]));
}
