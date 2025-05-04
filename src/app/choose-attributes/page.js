'use client';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';

export default function ChooseAttributes() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const site = searchParams.get('site');
  const keyword = searchParams.get('keyword');
  const [fields, setFields] = useState('title,price,rating');

  const handleScrape = () => {
    const query = `site=${site}&keyword=${keyword}&fields=${fields}`;
    router.push(`/results?${query}`);
  };

  return (
    <main className="p-6">
      <h2 className="text-2xl mb-4">Enter fields to scrape (comma-separated)</h2>
      <input
        value={fields}
        onChange={(e) => setFields(e.target.value)}
        className="border p-2 w-full"
      />
      <button onClick={handleScrape} className="mt-4 bg-blue-600 text-white px-4 py-2 rounded">Start Scraping</button>
    </main>
  );
}