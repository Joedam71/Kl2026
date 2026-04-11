import { useEffect, useMemo, useState } from 'react';
import { mediaApi } from '../api/client';
import { useStore } from '../store/useStore';
import { parseGenres } from '../types';
import MediaRow from '../components/MediaRow';
import MediaCard from '../components/MediaCard';

type SortKey = 'title' | 'year' | 'rating' | 'added';

export default function Movies() {
  const { allMedia, setAllMedia } = useStore();
  const [genre, setGenre] = useState<string | null>(null);
  const [sort, setSort] = useState<SortKey>('title');

  useEffect(() => {
    mediaApi.getAll({ type: 'movie' }).then(setAllMedia).catch(() => {});
  }, []);

  const movies = useMemo(() => allMedia.filter(m => m.type === 'movie'), [allMedia]);

  const genres = useMemo(() => {
    const set = new Set<string>();
    for (const m of movies) parseGenres(m.genres).forEach(g => set.add(g));
    return [...set].sort();
  }, [movies]);

  const filtered = useMemo(() => {
    let list = genre ? movies.filter(m => parseGenres(m.genres).includes(genre)) : movies;
    return [...list].sort((a, b) => {
      if (sort === 'year')   return (b.year ?? 0) - (a.year ?? 0);
      if (sort === 'rating') return (b.rating ?? 0) - (a.rating ?? 0);
      if (sort === 'added')  return b.added_at - a.added_at;
      return a.title.localeCompare(b.title);
    });
  }, [movies, genre, sort]);

  // Group by genre if no filter selected
  const genreRows = useMemo(() => {
    if (genre) return [];
    const map = new Map<string, typeof movies>();
    for (const m of movies) {
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
  }, [movies, genre]);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Movies</h1>
      </div>

      {/* Genre filter pills */}
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

      {/* Sort control */}
      {genre && (
        <div style={{ padding: '0 4% 16px', display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: '0.85rem', color: 'var(--gray)' }}>Sort by:</span>
          {(['title','year','rating','added'] as SortKey[]).map(s => (
            <button
              key={s}
              onClick={() => setSort(s)}
              style={{
                background: sort === s ? 'var(--white)' : 'transparent',
                color: sort === s ? '#000' : 'var(--gray)',
                border: '1px solid rgba(255,255,255,0.2)',
                borderRadius: 4,
                padding: '4px 12px',
                fontSize: '0.8rem',
                textTransform: 'capitalize',
              }}
            >{s}</button>
          ))}
        </div>
      )}

      {movies.length === 0 ? (
        <div className="empty-state">
          <h3>No movies yet</h3>
          <p>Add a media directory in Settings and scan your library.</p>
        </div>
      ) : genre ? (
        <div style={{ padding: '0 4%' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, paddingTop: 8, paddingBottom: 40 }}>
            {filtered.map(item => <MediaCard key={item.id} item={item} />)}
          </div>
        </div>
      ) : (
        <div style={{ paddingBottom: 60 }}>
          {genreRows.map(([g, items]) => (
            <MediaRow key={g} title={g} items={items} />
          ))}
        </div>
      )}
    </div>
  );
}
