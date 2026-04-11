import { useStore } from '../store/useStore';
import MediaCard from '../components/MediaCard';

export default function Search() {
  const { searchQuery, searchResults } = useStore();

  return (
    <div className="page">
      <div className="page-header">
        <h1>
          {searchQuery
            ? `Results for "${searchQuery}"`
            : 'Search'}
        </h1>
      </div>

      {searchQuery && searchResults.length === 0 && (
        <div className="empty-state">
          <h3>No results</h3>
          <p>Try a different title or genre.</p>
        </div>
      )}

      {searchResults.length > 0 && (
        <div style={{ padding: '16px 4%' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, paddingBottom: 60 }}>
            {searchResults.map(item => (
              <MediaCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
