import { useEffect } from 'react';
import { X, Play, Film } from 'lucide-react';
import { useStore } from '../store/useStore';
import { parseGenres, formatRuntime } from '../types';

export default function DetailModal() {
  const { modalItem, closeModal, play } = useStore();

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') closeModal(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [closeModal]);

  // Prevent body scroll
  useEffect(() => {
    if (modalItem) document.body.style.overflow = 'hidden';
    return () => { document.body.style.overflow = ''; };
  }, [modalItem]);

  if (!modalItem) return null;

  const genres = parseGenres(modalItem.genres);
  const rating = modalItem.rating ? (modalItem.rating / 2).toFixed(1) : null;
  const matchPct = modalItem.rating ? Math.round((modalItem.rating / 10) * 100) : null;

  return (
    <div className="modal-overlay" onClick={closeModal}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        {/* Backdrop */}
        <div style={{ position: 'relative' }}>
          {modalItem.backdrop_path ? (
            <img
              src={modalItem.backdrop_path}
              alt={modalItem.title}
              className="modal__backdrop"
            />
          ) : modalItem.poster_path ? (
            <img
              src={modalItem.poster_path}
              alt={modalItem.title}
              className="modal__backdrop"
              style={{ objectPosition: 'top center' }}
            />
          ) : (
            <div className="modal__backdrop-placeholder">
              <Film size={48} color="#555" />
            </div>
          )}
          <div className="modal__backdrop-gradient" />
        </div>

        {/* Close button */}
        <button className="modal__close" onClick={closeModal} aria-label="Close">
          <X size={18} />
        </button>

        {/* Content */}
        <div className="modal__content">
          <div className="modal__actions">
            <button className="btn btn--play" onClick={() => play(modalItem.id)}>
              <Play size={18} fill="currentColor" /> Play
            </button>
          </div>

          <h2 className="modal__title">{modalItem.title}</h2>

          <div className="modal__meta">
            {matchPct && <span className="modal__match">{matchPct}% Match</span>}
            {modalItem.year && <span className="modal__year">{modalItem.year}</span>}
            {modalItem.runtime && (
              <span className="modal__runtime">{formatRuntime(modalItem.runtime)}</span>
            )}
            {rating && (
              <span className="modal__badge" title="Rating">★ {rating}</span>
            )}
            {modalItem.type === 'show' && (
              <span className="modal__badge">
                {modalItem.season ? `Season ${modalItem.season}` : 'TV Series'}
              </span>
            )}
            <span className="modal__badge" style={{ textTransform: 'capitalize' }}>
              {modalItem.type === 'show' ? 'TV Show' : 'Movie'}
            </span>
          </div>

          {modalItem.overview && (
            <p className="modal__overview">{modalItem.overview}</p>
          )}

          {genres.length > 0 && (
            <div className="modal__tags">
              {genres.map(g => (
                <span key={g} className="modal__tag">{g}</span>
              ))}
            </div>
          )}

          <p className="modal__file">
            📁 {modalItem.file_path}
          </p>
        </div>
      </div>
    </div>
  );
}
