'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function SelectSite() {
  const [site, setSite] = useState('');
  const router = useRouter();

  const handleNext = () => {
    if (site) router.push(`/enter-keyword?site=${site}`);
  };

  return (
    <main className="p-6">
      <h2 className="text-2xl mb-4">Select a website</h2>
      <select value={site} onChange={(e) => setSite(e.target.value)} className="border p-2">
        <option value="">-- Choose --</option>
        <option value="amazon">Amazon</option>
        <option value="flipkart">Flipkart</option>
        <option value="nykaa">Nykaa</option>
      </select>
      <button onClick={handleNext} className="ml-4 bg-green-600 text-white px-4 py-2 rounded">Next</button>
    </main>
  );
}
