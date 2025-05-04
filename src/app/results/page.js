'use client';
import { useSearchParams } from 'next/navigation';
import { useEffect, useState } from 'react';

export default function Results() {
  const [data, setData] = useState([]);
  const searchParams = useSearchParams();
  const site = searchParams.get('site');
  const keyword = searchParams.get('keyword');
  const fields = searchParams.get('fields');

  useEffect(() => {
    fetch('/api/scrape', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ site, keyword, fields }),
    })
      .then((res) => res.json())
      .then(setData);
  }, []);

  return (
    <main className="p-6">
      <h2 className="text-2xl mb-4">Scraped Results</h2>
      <pre className="bg-gray-100 p-4 overflow-x-auto">
        {JSON.stringify(data, null, 2)}
      </pre>
    </main>
  );
}