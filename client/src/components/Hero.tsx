import { useEffect, useState } from 'react';
import { Play, Info } from 'lucide-react';
import { mediaApi } from '../api/client';
import { useStore } from '../store/useStore';
import { type Media, parseGenres, formatRuntime } from '../types';

export default function Hero() {
  const [featured, setFeatured] = useState<Media | null>(null);
  const { play, openModal } = useStore();

  useEffect(() => {
    mediaApi.getFeatured().then(item => {
      if (item) setFeatured(item);
    }).catch(() => {});
  }, []);

  if (!featured) {
    return (
      <div className="hero">
        <div className="hero__placeholder" />
        <div className="hero__gradient" />
        <div className="hero__content">
          <p className="hero__badge">KL2026</p>
          <h1 className="hero__title">Your Media Library</h1>
          <p className="hero__overview">
            Add your media directories in Settings and scan to start building your library.
          </p>
        </div>
      </div>
    );
  }

  const genres = parseGenres(featured.genres).slice(0, 3);
  const rating = featured.rating ? (featured.rating / 2).toFixed(1) : null;

  return (
    <div className="hero">
      {featured.backdrop_path ? (
        <img
          src={featured.backdrop_path}
          alt={featured.title}
          className="hero__backdrop"
          loading="eager"
        />
      ) : featured.poster_path ? (
        <img
          src={featured.poster_path}
          alt={featured.title}
          className="hero__backdrop"
          style={{ objectPosition: 'top center' }}
          loading="eager"
        />
      ) : (
        <div className="hero__placeholder" />
      )}

      <div className="hero__gradient" />

      <div className="hero__content">
        <p className="hero__badge">
          {featured.type === 'show' ? 'TV Series' : 'Movie'}
        </p>

        <h1 className="hero__title">{featured.title}</h1>

        <div className="hero__meta">
          {rating && <span className="hero__rating">★ {rating}</span>}
          {featured.year && <span>{featured.year}</span>}
          {featured.runtime && <span>{formatRuntime(featured.runtime)}</span>}
          {genres.map(g => <span key={g}>{g}</span>)}
        </div>

        {featured.overview && (
          <p className="hero__overview">{featured.overview}</p>
        )}

        <div className="hero__actions">
          <button className="btn btn--play" onClick={() => play(featured.id)}>
            <Play size={18} fill="currentColor" /> Play
          </button>
          <button className="btn btn--info" onClick={() => openModal(featured)}>
            <Info size={18} /> More Info
          </button>
        </div>
      </div>
    </div>
  );
}
