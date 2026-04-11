import { useEffect, useRef, useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { Search, X } from 'lucide-react';
import { useStore } from '../store/useStore';
import { searchApi } from '../api/client';

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const { isSearchOpen, setSearchOpen, searchQuery, setSearchQuery, setSearchResults } = useStore();
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  useEffect(() => {
    if (isSearchOpen) inputRef.current?.focus();
  }, [isSearchOpen]);

  function handleSearchChange(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setSearchQuery(q);

    if (searchTimer.current) clearTimeout(searchTimer.current);
    if (!q.trim()) { setSearchResults([]); return; }

    searchTimer.current = setTimeout(async () => {
      const results = await searchApi.query(q);
      setSearchResults(results);
      if (q.trim()) navigate('/search');
    }, 300);
  }

  function handleClose() {
    setSearchOpen(false);
    navigate('/');
  }

  return (
    <nav className={`navbar ${scrolled ? 'navbar--scrolled' : 'navbar--transparent'}`}>
      <NavLink to="/" className="navbar__logo">KL2026</NavLink>

      <ul className="navbar__links">
        <li><NavLink to="/" end>Home</NavLink></li>
        <li><NavLink to="/movies">Movies</NavLink></li>
        <li><NavLink to="/tv">TV Shows</NavLink></li>
      </ul>

      <div className="navbar__right">
        <div className="search-container">
          <div className={`search-input-wrap ${isSearchOpen ? 'open' : ''}`}>
            <Search size={16} color="#aaa" />
            <input
              ref={inputRef}
              type="text"
              placeholder="Titles, genres…"
              value={searchQuery}
              onChange={handleSearchChange}
              onKeyDown={e => e.key === 'Escape' && handleClose()}
            />
          </div>
          {isSearchOpen ? (
            <button className="search-toggle" onClick={handleClose} title="Close search">
              <X size={20} />
            </button>
          ) : (
            <button className="search-toggle" onClick={() => setSearchOpen(true)} title="Search">
              <Search size={20} />
            </button>
          )}
        </div>

        <NavLink to="/settings" title="Settings" style={{ display: 'flex', alignItems: 'center' }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
          </svg>
        </NavLink>
      </div>
    </nav>
  );
}
