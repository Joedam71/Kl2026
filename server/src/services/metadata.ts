import { updateMediaMetadata, getMediaById } from '../db/queries';
import { searchMovie, searchShow, buildImageUrl } from './tmdb';

export async function fetchAndStoreMetadata(
  mediaId: number,
  title: string,
  type: 'movie' | 'show',
  year?: number | null
): Promise<void> {
  try {
    if (type === 'movie') {
      const movie = await searchMovie(title, year);
      if (!movie) return;

      updateMediaMetadata(mediaId, {
        title: movie.title,
        tmdb_id: movie.id,
        overview: movie.overview || null,
        poster_path: buildImageUrl(movie.poster_path, 'w500'),
        backdrop_path: buildImageUrl(movie.backdrop_path, 'original'),
        genres: JSON.stringify(movie.genres.map(g => g.name)),
        rating: movie.vote_average || null,
        runtime: movie.runtime || null,
      });
      console.log(`[metadata] Updated movie: ${movie.title}`);
    } else {
      const show = await searchShow(title, year);
      if (!show) return;

      updateMediaMetadata(mediaId, {
        title: show.name,
        tmdb_id: show.id,
        overview: show.overview || null,
        poster_path: buildImageUrl(show.poster_path, 'w500'),
        backdrop_path: buildImageUrl(show.backdrop_path, 'original'),
        genres: JSON.stringify(show.genres.map(g => g.name)),
        rating: show.vote_average || null,
        runtime: show.episode_run_time?.[0] || null,
      });
      console.log(`[metadata] Updated show: ${show.name}`);
    }
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    if (msg.includes('401')) {
      console.error('[metadata] Invalid TMDb API key');
    } else {
      console.warn(`[metadata] Error for "${title}": ${msg}`);
    }
  }
}

export async function refreshMetadata(mediaId: number): Promise<void> {
  const item = getMediaById(mediaId);
  if (!item) throw new Error(`Media ${mediaId} not found`);
  await fetchAndStoreMetadata(mediaId, item.title, item.type as 'movie' | 'show', item.year);
}
