import { Play, Info } from 'lucide-react';
import { type Media, progressPercent } from '../types';
import { useStore } from '../store/useStore';

interface Props {
  item: Media;
}

export default function MediaCard({ item }: Props) {
  const { play, openModal } = useStore();
  const pct = progressPercent(item);

  return (
    <div className="media-card" role="button" tabIndex={0} onClick={() => openModal(item)}
      onKeyDown={e => e.key === 'Enter' && openModal(item)}>

      {item.poster_path ? (
        <img
          src={item.poster_path}
          alt={item.title}
          className="media-card__poster"
          loading="lazy"
        />
      ) : (
        <div className="media-card__placeholder">
          <span style={{ fontSize: '2rem' }}>🎬</span>
          <span>{item.title}</span>
        </div>
      )}

      {/* Progress bar for in-progress items */}
      {pct > 0 && pct < 95 && (
        <div className="media-card__progress">
          <div className="media-card__progress-bar" style={{ width: `${pct}%` }} />
        </div>
      )}

      {/* Hover overlay */}
      <div className="media-card__overlay">
        <div className="media-card__actions" onClick={e => e.stopPropagation()}>
          <button
            className="media-card__btn media-card__btn--play"
            onClick={() => play(item.id)}
            title="Play"
          >
            <Play size={13} fill="currentColor" />
          </button>
          <button
            className="media-card__btn"
            onClick={() => openModal(item)}
            title="More info"
          >
            <Info size={13} />
          </button>
        </div>

        <div className="media-card__title">{item.title}</div>

        <div className="media-card__meta">
          {item.rating && (
            <span className="media-card__rating">
              ★ {(item.rating / 2).toFixed(1)}
            </span>
          )}
          {item.year && <span>{item.year}</span>}
          {item.type === 'show' && item.season && (
            <span>S{String(item.season).padStart(2, '0')}</span>
          )}
        </div>
      </div>
    </div>
  );
}
