import { Router } from 'express';
import { getSetting } from '../db/queries';
import { scanDirectories } from '../services/scanner';

const router = Router();

// POST /api/scan  — trigger a library scan against configured media_dirs
router.post('/', async (_req, res) => {
  const raw = getSetting('media_dirs');
  let dirs: string[] = [];
  try {
    dirs = raw ? (JSON.parse(raw) as string[]) : [];
  } catch {
    dirs = [];
  }

  if (dirs.length === 0) {
    return res.status(400).json({ error: 'No media directories configured. Add them in Settings first.' });
  }

  // Respond immediately so the client isn't waiting
  res.json({ ok: true, message: 'Scan started', dirs });

  // Run in background
  scanDirectories(dirs)
    .then(({ added, skipped }) => {
      console.log(`[scan] Done — added: ${added}, skipped: ${skipped}`);
    })
    .catch(err => console.error('[scan] Error:', err));
});

export default router;
