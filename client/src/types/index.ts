export interface Media {
  id: number;
  file_path: string;
  type: 'movie' | 'show';
  title: string;
  year: number | null;
  tmdb_id: number | null;
  overview: string | null;
  poster_path: string | null;
  backdrop_path: string | null;
  genres: string | null; // JSON string array e.g. '["Action","Drama"]'
  rating: number | null;
  runtime: number | null;
  season: number | null;
  episode: number | null;
  added_at: number;
  last_scanned: number;
  // Joined from progress table (on some endpoints)
  position_seconds?: number;
  duration_seconds?: number;
}

export interface Progress {
  media_id: number;
  position_seconds: number;
  duration_seconds: number;
  updated_at?: number;
}

export interface AppSettings {
  media_dirs: string;    // JSON string array
  tmdb_api_key: string;
  tmdb_image_base: string;
}

export function parseGenres(genres: string | null): string[] {
  if (!genres) return [];
  try {
    return JSON.parse(genres) as string[];
  } catch {
    // Legacy: comma-separated
    return genres.split(',').map(g => g.trim()).filter(Boolean);
  }
}

export function progressPercent(p?: Pick<Media, 'position_seconds' | 'duration_seconds'>): number {
  if (!p?.duration_seconds || !p?.position_seconds) return 0;
  return Math.min(100, (p.position_seconds / p.duration_seconds) * 100);
}

export function formatRuntime(minutes: number | null): string {
  if (!minutes) return '';
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}
