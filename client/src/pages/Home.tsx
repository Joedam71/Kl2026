import { useEffect, useMemo } from 'react';
import { mediaApi, progressApi } from '../api/client';
import { useStore } from '../store/useStore';
import { parseGenres } from '../types';
import Hero from '../components/Hero';
import MediaRow from '../components/MediaRow';

export default function Home() {
  const { allMedia, setAllMedia, continueWatching, setContinueWatching } = useStore();

  useEffect(() => {
    mediaApi.getAll().then(setAllMedia).catch(() => {});
    progressApi.getAll().then(setContinueWatching).catch(() => {});
  }, []);

  const movies = useMemo(() => allMedia.filter(m => m.type === 'movie'), [allMedia]);
  const shows  = useMemo(() => allMedia.filter(m => m.type === 'show'),  [allMedia]);

  const recentlyAdded = useMemo(
    () => [...allMedia].sort((a, b) => b.added_at - a.added_at).slice(0, 30),
    [allMedia]
  );

  // Build genre rows from all media (top 6 genres)
  const genreRows = useMemo(() => {
    const genreMap = new Map<string, typeof allMedia>();
    for (const item of allMedia) {
      for (const g of parseGenres(item.genres)) {
        if (!genreMap.has(g)) genreMap.set(g, []);
        genreMap.get(g)!.push(item);
      }
    }
    return [...genreMap.entries()]
      .filter(([, items]) => items.length >= 3)
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, 6);
  }, [allMedia]);

  const hasContent = allMedia.length > 0;

  return (
    <div className="page">
      <Hero />

      <div className="home-rows">
        {!hasContent && (
          <div className="empty-state" style={{ marginTop: 40 }}>
            <h3>Your library is empty</h3>
            <p>Go to Settings to add media directories, then scan your library to get started.</p>
            <a href="/settings" className="btn btn--red" style={{ marginTop: 12 }}>
              Open Settings
            </a>
          </div>
        )}

        {continueWatching.length > 0 && (
          <MediaRow title="Continue Watching" items={continueWatching} />
        )}

        {recentlyAdded.length > 0 && (
          <MediaRow title="Recently Added" items={recentlyAdded} />
        )}

        {movies.length > 0 && (
          <MediaRow title="Movies" items={movies} />
        )}

        {shows.length > 0 && (
          <MediaRow title="TV Shows" items={shows} />
        )}

        {genreRows.map(([genre, items]) => (
          <MediaRow key={genre} title={genre} items={items} />
        ))}
      </div>
    </div>
  );
}
