import { Router } from 'express';
import { searchMedia } from '../db/queries';

const router = Router();

// GET /api/search?q=&type=
router.get('/', (req, res) => {
  const { q, type } = req.query as Record<string, string>;

  if (!q || q.trim().length < 1) {
    return res.json([]);
  }

  const results = searchMedia(q.trim(), type);
  res.json(results);
});

export default router;
