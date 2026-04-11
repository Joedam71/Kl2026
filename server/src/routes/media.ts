import { Router } from 'express';
import { getAllMedia, getMediaById, getFeatured, getGenres, deleteMedia } from '../db/queries';
import { refreshMetadata } from '../services/metadata';

const router = Router();

// GET /api/media  — list with optional ?type=movie|show&genre=Action
router.get('/', (req, res) => {
  const { type, genre } = req.query as Record<string, string>;
  const items = getAllMedia({ type, genre });
  res.json(items);
});

// GET /api/media/featured
router.get('/featured', (_req, res) => {
  res.json(getFeatured() ?? null);
});

// GET /api/media/genres
router.get('/genres', (_req, res) => {
  res.json(getGenres());
});

// GET /api/media/:id
router.get('/:id', (req, res) => {
  const item = getMediaById(Number(req.params.id));
  if (!item) return res.status(404).json({ error: 'Not found' });
  res.json(item);
});

// POST /api/media/:id/refresh  — re-fetch TMDb metadata
router.post('/:id/refresh', async (req, res) => {
  try {
    await refreshMetadata(Number(req.params.id));
    const updated = getMediaById(Number(req.params.id));
    res.json(updated);
  } catch (err: unknown) {
    res.status(500).json({ error: err instanceof Error ? err.message : String(err) });
  }
});

// DELETE /api/media/:id  — remove from library (does NOT delete file)
router.delete('/:id', (req, res) => {
  deleteMedia(Number(req.params.id));
  res.json({ ok: true });
});

export default router;
