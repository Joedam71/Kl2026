import express from 'express';
import cors from 'cors';
import path from 'path';
import dotenv from 'dotenv';
import { initDb } from './db/schema';
import mediaRouter from './routes/media';
import streamRouter from './routes/stream';
import scanRouter from './routes/scan';
import progressRouter from './routes/progress';
import searchRouter from './routes/search';
import settingsRouter from './routes/settings';

dotenv.config({ path: path.resolve(__dirname, '../../.env') });

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json());

// Initialize database on startup
initDb();

// API routes
app.use('/api/media', mediaRouter);
app.use('/api/stream', streamRouter);
app.use('/api/scan', scanRouter);
app.use('/api/progress', progressRouter);
app.use('/api/search', searchRouter);
app.use('/api/settings', settingsRouter);

// Serve built client in production
if (process.env.NODE_ENV === 'production') {
  const clientDist = path.resolve(__dirname, '../../client/dist');
  app.use(express.static(clientDist));
  app.get('*', (_req, res) => {
    res.sendFile(path.join(clientDist, 'index.html'));
  });
}

app.listen(PORT, () => {
  console.log(`\n🎬 KL2026 Media Server running at http://localhost:${PORT}\n`);
});
