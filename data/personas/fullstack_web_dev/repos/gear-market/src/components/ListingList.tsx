import { useEffect, useState } from "react";

type Listing = { id: string; title: string; price: number };

export function ListingList({ ownerId }: { ownerId: string }) {
  const [items, setItems] = useState<Listing[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/listings?owner=${ownerId}`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setItems)
      .catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => controller.abort();
  }, [ownerId]);

  if (error) return <p role="alert">Could not load: {error}</p>;
  if (items.length === 0) return <p>Nothing here yet.</p>;
  return (
    <ul className="divide-y">
      {items.map((item) => (
        <li key={item.id} className="flex justify-between py-2">
          <span>{item.title}</span>
          <span>{item.price.toFixed(2)}</span>
        </li>
      ))}
    </ul>
  );
}
