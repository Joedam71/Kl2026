import { useRef } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { type Media } from '../types';
import MediaCard from './MediaCard';

interface Props {
  title: string;
  items: Media[];
}

const SCROLL_AMOUNT = 600;

export default function MediaRow({ title, items }: Props) {
  const trackRef = useRef<HTMLDivElement>(null);

  if (!items.length) return null;

  function scroll(dir: 'left' | 'right') {
    if (!trackRef.current) return;
    trackRef.current.scrollBy({ left: dir === 'left' ? -SCROLL_AMOUNT : SCROLL_AMOUNT, behavior: 'smooth' });
  }

  return (
    <div className="media-row">
      <div className="media-row__header">
        <h2 className="media-row__title">{title}</h2>
        <span className="media-row__see-all">See all &rsaquo;</span>
      </div>

      <div className="media-row__track-wrapper">
        <button className="media-row__arrow media-row__arrow--left" onClick={() => scroll('left')} aria-label="Scroll left">
          <ChevronLeft size={20} />
        </button>

        <div className="media-row__track" ref={trackRef}>
          {items.map(item => (
            <MediaCard key={item.id} item={item} />
          ))}
        </div>

        <button className="media-row__arrow media-row__arrow--right" onClick={() => scroll('right')} aria-label="Scroll right">
          <ChevronRight size={20} />
        </button>
      </div>
    </div>
  );
}
