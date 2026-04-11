import fg from 'fast-glob';
import path from 'path';
import { insertMedia, getMediaByPath } from '../db/queries';
import { fetchAndStoreMetadata } from './metadata';

const VIDEO_EXTS = ['mp4', 'mkv', 'avi', 'mov', 'wmv', 'm4v', 'ts', 'webm', 'flv', 'mpg', 'mpeg', 'vob', 'divx'];

interface ParsedFilename {
  title: string;
  year: number | null;
  type: 'movie' | 'show';
  season: number | null;
  episode: number | null;
}

export function parseFilename(filePath: string): ParsedFilename {
  const basename = path.basename(filePath, path.extname(filePath));

  // Detect season/episode: S01E01, s01e01
  const seEpMatch = basename.match(/[Ss](\d{1,2})[Ee](\d{1,3})/);
  // Alt: 1x01
  const altMatch = !seEpMatch ? basename.match(/(\d{1,2})x(\d{2,3})/i) : null;

  const season = seEpMatch ? parseInt(seEpMatch[1]) : altMatch ? parseInt(altMatch[1]) : null;
  const episode = seEpMatch ? parseInt(seEpMatch[2]) : altMatch ? parseInt(altMatch[2]) : null;
  const type: 'movie' | 'show' = season !== null ? 'show' : 'movie';

  // Strip episode info from title
  let titleRaw = basename;
  if (seEpMatch) titleRaw = titleRaw.slice(0, titleRaw.search(/[Ss]\d{1,2}[Ee]\d{1,3}/i));
  else if (altMatch) titleRaw = titleRaw.slice(0, titleRaw.search(/\d{1,2}x\d{2,3}/i));

  // Extract year
  const yearMatch = titleRaw.match(/[(\[.\s](\d{4})[)\].\s]/) || titleRaw.match(/\b(19\d{2}|20\d{2})\b/);
  const year = yearMatch ? parseInt(yearMatch[1]) : null;
  if (year) {
    titleRaw = titleRaw.slice(0, titleRaw.search(new RegExp(`[.(\\[]?${year}`))).trim();
  }

  // Clean up dots, underscores, extra spaces
  const title = titleRaw.replace(/[._\-]+/g, ' ').replace(/\s+/g, ' ').trim() || basename;

  return { title, year, type, season, episode };
}

export async function scanDirectories(dirs: string[]): Promise<{ added: number; skipped: number }> {
  const patterns = dirs.flatMap(dir =>
    VIDEO_EXTS.map(ext => `${dir.replace(/\\/g, '/')}/**/*.${ext}`)
  );

  let added = 0;
  let skipped = 0;

  let files: string[] = [];
  try {
    files = await fg(patterns, {
      caseSensitiveMatch: false,
      suppressErrors: true,
      dot: false,
      unique: true,
    });
  } catch (err) {
    console.error('Glob error:', err);
  }

  console.log(`Scan found ${files.length} video files`);

  for (const file of files) {
    const existing = getMediaByPath(file);
    if (existing) {
      skipped++;
      continue;
    }

    const parsed = parseFilename(file);

    const id = insertMedia({
      file_path: file,
      type: parsed.type,
      title: parsed.title,
      year: parsed.year,
      tmdb_id: null,
      overview: null,
      poster_path: null,
      backdrop_path: null,
      genres: null,
      rating: null,
      runtime: null,
      season: parsed.season,
      episode: parsed.episode,
    });

    // Fire-and-forget metadata enrichment
    if (id) {
      fetchAndStoreMetadata(id, parsed.title, parsed.type, parsed.year).catch(err =>
        console.warn(`Metadata fetch failed for "${parsed.title}": ${err.message}`)
      );
    }

    added++;
  }

  return { added, skipped };
}
