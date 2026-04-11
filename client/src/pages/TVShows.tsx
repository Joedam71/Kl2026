import { useEffect, useMemo, useState } from 'react';
import { mediaApi } from '../api/client';
import { useStore } from '../store/useStore';
import { parseGenres } from '../types';
import MediaRow from '../components/MediaRow';
import MediaCard from '../components/MediaCard';

export default function TVShows() {
  const { allMedia, setAllMedia } = useStore();
  const [genre, setGenre] = useState<string | null>(null);

  useEffect(() => {
    mediaApi.getAll({ type: 'show' }).then(setAllMedia).catch(() => {});
  }, []);

  const shows = useMemo(() => allMedia.filter(m => m.type === 'show'), [allMedia]);

  const genres = useMemo(() => {
    const set = new Set<string>();
    for (const m of shows) parseGenres(m.genres).forEach(g => set.add(g));
    return [...set].sort();
  }, [shows]);

  const filtered = useMemo(
    () => genre ? shows.filter(m => parseGenres(m.genres).includes(genre)) : shows,
    [shows, genre]
  );

  // Group by series title (collapse episodes)
  const seriesMap = useMemo(() => {
    const map = new Map<string, typeof shows>();
    for (const m of shows) {
      const key = m.title;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(m);
    }
    return map;
  }, [shows]);

  // Get one representative per series (first episode or best-rated)
  const seriesList = useMemo(() => {
    return [...seriesMap.values()].map(episodes =>
      episodes.sort((a, b) => (a.season ?? 0) - (b.season ?? 0) || (a.episode ?? 0) - (b.episode ?? 0))[0]
    );
  }, [seriesMap]);

  const displayList = genre ? filtered : seriesList;

  const genreRows = useMemo(() => {
    if (genre) return [];
    const map = new Map<string, typeof seriesList>();
    for (const m of seriesList) {
      const gs = parseGenres(m.genres);
      if (!gs.length) {
        if (!map.has('Other')) map.set('Other', []);
        map.get('Other')!.push(m);
      }
      for (const g of gs) {
        if (!map.has(g)) map.set(g, []);
        map.get(g)!.push(m);
      }
    }
    return [...map.entries()].filter(([, items]) => items.length > 0);
  }, [seriesList, genre]);

  return (
    <div className="page">
      <div className="page-header">
        <h1>TV Shows</h1>
      </div>

      <div className="genre-filters">
        <button
          className={`genre-pill ${!genre ? 'active' : ''}`}
          onClick={() => setGenre(null)}
        >All</button>
        {genres.map(g => (
          <button
            key={g}
            className={`genre-pill ${genre === g ? 'active' : ''}`}
            onClick={() => setGenre(g)}
          >{g}</button>
        ))}
      </div>

      {shows.length === 0 ? (
        <div className="empty-state">
          <h3>No TV shows yet</h3>
          <p>Add a media directory in Settings and scan your library.</p>
        </div>
      ) : genre ? (
        <div style={{ padding: '0 4%' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, paddingTop: 8, paddingBottom: 40 }}>
            {displayList.map(item => <MediaCard key={item.id} item={item} />)}
          </div>
        </div>
      ) : (
        <div style={{ paddingBottom: 60 }}>
          {genreRows.length > 0
            ? genreRows.map(([g, items]) => <MediaRow key={g} title={g} items={items} />)
            : <MediaRow title="All TV Shows" items={seriesList} />
          }
        </div>
      )}
    </div>
  );
}
