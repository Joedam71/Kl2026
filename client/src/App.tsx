import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar from './components/Navbar';
import DetailModal from './components/DetailModal';
import VideoPlayer from './components/VideoPlayer';
import Home from './pages/Home';
import Movies from './pages/Movies';
import TVShows from './pages/TVShows';
import Search from './pages/Search';
import Settings from './pages/Settings';
import { useStore } from './store/useStore';

export default function App() {
  const playingId = useStore(s => s.playingId);

  return (
    <BrowserRouter>
      <div className="app">
        {/* Full-screen player overlays everything when active */}
        {playingId && <VideoPlayer />}

        {!playingId && (
          <>
            <Navbar />
            <Routes>
              <Route path="/"        element={<Home />} />
              <Route path="/movies"  element={<Movies />} />
              <Route path="/tv"      element={<TVShows />} />
              <Route path="/search"  element={<Search />} />
              <Route path="/settings" element={<Settings />} />
            </Routes>

            {/* Global detail modal */}
            <DetailModal />
          </>
        )}
      </div>
    </BrowserRouter>
  );
}
