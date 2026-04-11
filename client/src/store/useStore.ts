import { create } from 'zustand';
import type { Media } from '../types';

interface AppState {
  // Library cache
  allMedia: Media[];
  setAllMedia: (items: Media[]) => void;

  // Currently open detail modal
  modalItem: Media | null;
  openModal: (item: Media) => void;
  closeModal: () => void;

  // Currently playing media (navigates to /play/:id)
  playingId: number | null;
  play: (id: number) => void;
  stopPlaying: () => void;

  // Search
  searchQuery: string;
  setSearchQuery: (q: string) => void;
  searchResults: Media[];
  setSearchResults: (items: Media[]) => void;
  isSearchOpen: boolean;
  setSearchOpen: (open: boolean) => void;

  // Continue watching items (joined with progress)
  continueWatching: Media[];
  setContinueWatching: (items: Media[]) => void;
}

export const useStore = create<AppState>((set) => ({
  allMedia: [],
  setAllMedia: (items) => set({ allMedia: items }),

  modalItem: null,
  openModal: (item) => set({ modalItem: item }),
  closeModal: () => set({ modalItem: null }),

  playingId: null,
  play: (id) => set({ playingId: id, modalItem: null }),
  stopPlaying: () => set({ playingId: null }),

  searchQuery: '',
  setSearchQuery: (q) => set({ searchQuery: q }),
  searchResults: [],
  setSearchResults: (items) => set({ searchResults: items }),
  isSearchOpen: false,
  setSearchOpen: (open) => set({ isSearchOpen: open, ...(!open && { searchQuery: '', searchResults: [] }) }),

  continueWatching: [],
  setContinueWatching: (items) => set({ continueWatching: items }),
}));
