import { Router } from 'express';
import path from 'path';
import fs from 'fs';
import { getAllSettings, setSetting } from '../db/queries';

const router = Router();

// GET /api/settings
router.get('/', (_req, res) => {
  res.json(getAllSettings());
});

// POST /api/settings  body: { media_dirs: string[], tmdb_api_key: string }
router.post('/', (req, res) => {
  const body = req.body as Record<string, unknown>;

  if ('media_dirs' in body) {
    const dirs = body.media_dirs as string[];
    if (!Array.isArray(dirs)) {
      return res.status(400).json({ error: 'media_dirs must be an array' });
    }
    // Validate each path exists
    const invalid = dirs.filter(d => !fs.existsSync(path.resolve(d)));
    if (invalid.length > 0) {
      return res.status(400).json({ error: `Paths do not exist: ${invalid.join(', ')}` });
    }
    setSetting('media_dirs', JSON.stringify(dirs.map(d => path.resolve(d))));
  }

  if ('tmdb_api_key' in body) {
    setSetting('tmdb_api_key', String(body.tmdb_api_key ?? ''));
  }

  if ('tmdb_image_base' in body) {
    setSetting('tmdb_image_base', String(body.tmdb_image_base ?? 'https://image.tmdb.org/t/p'));
  }

  res.json({ ok: true, settings: getAllSettings() });
});

export default router;
