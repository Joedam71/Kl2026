import axios from 'axios';
import { getSetting } from '../db/queries';

const TMDB_BASE = 'https://api.themoviedb.org/3';

function getApiKey(): string | null {
  return getSetting('tmdb_api_key') || process.env.TMDB_API_KEY || null;
}

export interface TmdbMovie {
  id: number;
  title: string;
  original_title: string;
  overview: string;
  poster_path: string | null;
  backdrop_path: string | null;
  release_date: string;
  vote_average: number;
  runtime: number | null;
  genres: { id: number; name: string }[];
}

export interface TmdbShow {
  id: number;
  name: string;
  original_name: string;
  overview: string;
  poster_path: string | null;
  backdrop_path: string | null;
  first_air_date: string;
  vote_average: number;
  episode_run_time: number[];
  genres: { id: number; name: string }[];
}

export async function searchMovie(title: string, year?: number | null): Promise<TmdbMovie | null> {
  const apiKey = getApiKey();
  if (!apiKey) return null;

  const params: Record<string, string | number> = { api_key: apiKey, query: title };
  if (year) params.year = year;

  const res = await axios.get<{ results: TmdbMovie[] }>(`${TMDB_BASE}/search/movie`, { params, timeout: 8000 });
  const results = res.data.results;
  if (!results?.length) return null;

  const detail = await axios.get<TmdbMovie>(`${TMDB_BASE}/movie/${results[0].id}`, {
    params: { api_key: apiKey },
    timeout: 8000,
  });
  return detail.data;
}

export async function searchShow(title: string, year?: number | null): Promise<TmdbShow | null> {
  const apiKey = getApiKey();
  if (!apiKey) return null;

  const params: Record<string, string | number> = { api_key: apiKey, query: title };
  if (year) params.first_air_date_year = year as number;

  const res = await axios.get<{ results: TmdbShow[] }>(`${TMDB_BASE}/search/tv`, { params, timeout: 8000 });
  const results = res.data.results;
  if (!results?.length) return null;

  const detail = await axios.get<TmdbShow>(`${TMDB_BASE}/tv/${results[0].id}`, {
    params: { api_key: apiKey },
    timeout: 8000,
  });
  return detail.data;
}

export function buildImageUrl(imagePath: string | null, size = 'w500'): string | null {
  if (!imagePath) return null;
  const base = getSetting('tmdb_image_base') || 'https://image.tmdb.org/t/p';
  return `${base}/${size}${imagePath}`;
}
