import { Router } from 'express';
import { getProgress, upsertProgress, getContinueWatching } from '../db/queries';

const router = Router();

// GET /api/progress  — continue-watching list
router.get('/', (_req, res) => {
  res.json(getContinueWatching());
});

// GET /api/progress/:mediaId
router.get('/:mediaId', (req, res) => {
  const prog = getProgress(Number(req.params.mediaId));
  res.json(prog ?? { media_id: Number(req.params.mediaId), position_seconds: 0, duration_seconds: 0 });
});

// POST /api/progress/:mediaId  body: { position_seconds, duration_seconds }
router.post('/:mediaId', (req, res) => {
  const { position_seconds, duration_seconds } = req.body as {
    position_seconds: number;
    duration_seconds: number;
  };

  if (typeof position_seconds !== 'number' || typeof duration_seconds !== 'number') {
    return res.status(400).json({ error: 'position_seconds and duration_seconds are required numbers' });
  }

  upsertProgress(Number(req.params.mediaId), position_seconds, duration_seconds);
  res.json({ ok: true });
});

export default router;
