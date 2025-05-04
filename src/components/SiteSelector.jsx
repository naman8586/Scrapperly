'use client';
import { useContext } from 'react';
import { motion } from 'framer-motion';
import { ScraperContext } from './ScraperContext';

export default function SiteSelector() {
  const { selectedSite, setSelectedSite, setStep } = useContext(ScraperContext);
  const sites = [
    'Alibaba',
    'eBay',
    'DHgate',
    'Amazon',
    'Flipkart',
    'MadeInChina',
    'IndiaMart',
  ];

  const handleSelect = (site) => {
    setSelectedSite(site);
    setStep(2);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg"
    >
      <h2 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">
        Choose Website
      </h2>
      <select
        value={selectedSite}
        onChange={(e) => handleSelect(e.target.value)}
        className="w-full p-3 border rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
      >
        <option value="">Select a website</option>
        {sites.map((site) => (
          <option key={site} value={site}>
            {site}
          </option>
        ))}
      </select>
    </motion.div>
  );
}