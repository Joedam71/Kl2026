import { Router } from 'express';
import fs from 'fs';
import mime from 'mime-types';
import { getMediaById } from '../db/queries';

const router = Router();

// GET /api/stream/:id  — HTTP range-request video streaming
router.get('/:id', (req, res) => {
  const item = getMediaById(Number(req.params.id));
  if (!item) return res.status(404).json({ error: 'Not found' });

  const filePath = item.file_path;
  if (!fs.existsSync(filePath)) {
    return res.status(404).json({ error: 'File not found on disk' });
  }

  const stat = fs.statSync(filePath);
  const fileSize = stat.size;
  const contentType = (mime.lookup(filePath) || 'video/mp4') as string;

  const rangeHeader = req.headers.range;

  if (rangeHeader) {
    const [startStr, endStr] = rangeHeader.replace(/bytes=/, '').split('-');
    const start = parseInt(startStr, 10);
    const end = endStr ? parseInt(endStr, 10) : fileSize - 1;

    if (start >= fileSize || end >= fileSize) {
      res.status(416).set('Content-Range', `bytes */${fileSize}`).end();
      return;
    }

    const chunkSize = end - start + 1;
    res.writeHead(206, {
      'Content-Range': `bytes ${start}-${end}/${fileSize}`,
      'Accept-Ranges': 'bytes',
      'Content-Length': chunkSize,
      'Content-Type': contentType,
    });
    fs.createReadStream(filePath, { start, end }).pipe(res);
  } else {
    res.writeHead(200, {
      'Content-Length': fileSize,
      'Content-Type': contentType,
      'Accept-Ranges': 'bytes',
    });
    fs.createReadStream(filePath).pipe(res);
  }
});

export default router;
