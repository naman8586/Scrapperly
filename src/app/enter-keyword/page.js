'use client';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';

export default function EnterKeyword() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const site = searchParams.get('site');
  const [keyword, setKeyword] = useState('');

  const handleNext = () => {
    if (keyword) router.push(`/choose-attributes?site=${site}&keyword=${keyword}`);
  };

  return (
    <main className="p-6">
      <h2 className="text-2xl mb-4">Enter keyword to scrape</h2>
      <input
        value={keyword}
        onChange={(e) => setKeyword(e.target.value)}
        placeholder="e.g. Christian Dior perfume"
        className="border p-2 w-full"
      />
      <button onClick={handleNext} className="mt-4 bg-green-600 text-white px-4 py-2 rounded">Next</button>
    </main>
  );
}