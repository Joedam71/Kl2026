import { useEffect, useState } from 'react';
import { Trash2, Plus, RefreshCw, Check, AlertCircle } from 'lucide-react';
import { settingsApi, scanApi, mediaApi } from '../api/client';
import { useStore } from '../store/useStore';

export default function Settings() {
  const { allMedia } = useStore();
  const [dirs, setDirs] = useState<string[]>([]);
  const [newDir, setNewDir] = useState('');
  const [tmdbKey, setTmdbKey] = useState('');
  const [saving, setSaving] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ type: 'ok' | 'err'; text: string } | null>(null);
  const [scanMsg, setScanMsg] = useState<string | null>(null);

  useEffect(() => {
    settingsApi.get().then(s => {
      try { setDirs(JSON.parse(s.media_dirs)); } catch { setDirs([]); }
      setTmdbKey(s.tmdb_api_key ?? '');
    }).catch(() => {});
  }, []);

  function addDir() {
    const d = newDir.trim();
    if (!d || dirs.includes(d)) return;
    setDirs(prev => [...prev, d]);
    setNewDir('');
  }

  function removeDir(dir: string) {
    setDirs(prev => prev.filter(d => d !== dir));
  }

  async function save() {
    setSaving(true);
    setSaveMsg(null);
    try {
      await settingsApi.save({ media_dirs: dirs, tmdb_api_key: tmdbKey });
      setSaveMsg({ type: 'ok', text: 'Settings saved' });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Save failed';
      setSaveMsg({ type: 'err', text: msg });
    } finally {
      setSaving(false);
      setTimeout(() => setSaveMsg(null), 3000);
    }
  }

  async function scan() {
    // Save first so dirs are persisted
    await settingsApi.save({ media_dirs: dirs, tmdb_api_key: tmdbKey });
    setScanning(true);
    setScanMsg(null);
    try {
      const res = await scanApi.start();
      setScanMsg(res.message + ` (${res.dirs.length} dirs)`);
    } catch (err: unknown) {
      const msg = err instanceof Error
        ? (err as { response?: { data?: { error?: string } }; message: string }).response?.data?.error ?? err.message
        : 'Scan failed';
      setScanMsg(`Error: ${msg}`);
    } finally {
      setScanning(false);
    }
  }

  const movies = allMedia.filter(m => m.type === 'movie').length;
  const shows  = allMedia.filter(m => m.type === 'show').length;

  return (
    <div className="page">
      <div className="settings-page">
        <h1>Settings</h1>

        {/* Library stats */}
        <div className="settings-section">
          <h2>Library Stats</h2>
          <div className="stats-grid">
            <div className="stat-box"><span className="stat-num">{allMedia.length}</span><div className="stat-label">Total Items</div></div>
            <div className="stat-box"><span className="stat-num">{movies}</span><div className="stat-label">Movies</div></div>
            <div className="stat-box"><span className="stat-num">{shows}</span><div className="stat-label">TV Episodes</div></div>
          </div>
        </div>

        {/* Media directories */}
        <div className="settings-section">
          <h2>Media Directories</h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--gray)', marginBottom: 16, lineHeight: 1.6 }}>
            Add the folders where your video files are stored. Subdirectories are scanned recursively.
          </p>

          {dirs.length > 0 && (
            <ul className="dir-list">
              {dirs.map(dir => (
                <li key={dir}>
                  <span>📁</span>
                  <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{dir}</span>
                  <button onClick={() => removeDir(dir)} title="Remove">
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          )}

          <div style={{ display: 'flex', gap: 8 }}>
            <input
              type="text"
              value={newDir}
              onChange={e => setNewDir(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && addDir()}
              placeholder="/path/to/your/media"
              style={{
                flex: 1,
                background: 'var(--bg3)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 'var(--radius)',
                color: 'var(--white)',
                padding: '10px 14px',
                fontSize: '0.9rem',
                fontFamily: 'monospace',
              }}
            />
            <button className="btn btn--ghost" onClick={addDir}>
              <Plus size={16} /> Add
            </button>
          </div>

          <div style={{ marginTop: 20, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
            <button className="btn btn--red" onClick={scan} disabled={scanning}>
              <RefreshCw size={16} style={scanning ? { animation: 'spin 1s linear infinite' } : {}} />
              {scanning ? 'Scanning…' : 'Scan Library'}
            </button>
            {scanMsg && (
              <span style={{ fontSize: '0.85rem', color: scanMsg.startsWith('Error') ? '#f44' : '#46d369' }}>
                {scanMsg}
              </span>
            )}
          </div>
        </div>

        {/* TMDb API */}
        <div className="settings-section">
          <h2>TMDb Metadata</h2>
          <div className="settings-field">
            <label>API Key</label>
            <input
              type="password"
              value={tmdbKey}
              onChange={e => setTmdbKey(e.target.value)}
              placeholder="Enter your TMDb API key"
            />
            <p className="hint">
              Get a free API key from themoviedb.org. Used to fetch posters, backdrops, and metadata.
              Leave blank to use filenames only.
            </p>
          </div>
        </div>

        {/* Save button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <button className="btn btn--red" onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save Settings'}
          </button>
          {saveMsg && (
            <span style={{
              display: 'flex', alignItems: 'center', gap: 6,
              fontSize: '0.85rem',
              color: saveMsg.type === 'ok' ? '#46d369' : '#f44'
            }}>
              {saveMsg.type === 'ok' ? <Check size={15} /> : <AlertCircle size={15} />}
              {saveMsg.text}
            </span>
          )}
        </div>
      </div>

      <style>{`
        @keyframes spin { to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
