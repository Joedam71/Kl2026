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
  genres: string | null; // JSON string array
  rating: number | null;
  runtime: number | null;
  season: number | null;
  episode: number | null;
  added_at: number;
  last_scanned: number;
}

export interface Progress {
  id: number;
  media_id: number;
  position_seconds: number;
  duration_seconds: number;
  updated_at: number;
}

export interface Settings {
  media_dirs: string[];
  tmdb_api_key: string;
  tmdb_image_base: string;
}
