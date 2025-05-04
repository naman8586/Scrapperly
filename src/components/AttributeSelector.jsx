'use client';
import { useContext } from 'react';
import { motion } from 'framer-motion';
import { ScraperContext } from './ScraperContext';

export default function AttributeSelector() {
  const { attributes, setAttributes, setStep, selectedSite } = useContext(ScraperContext);
  const allAttributes = ['username', 'price', 'image', 'description', 'rating', 'title'];

  const toggleAttribute = (attr) => {
    setAttributes((prev) =>
      prev.includes(attr) ? prev.filter((a) => a !== attr) : [...prev, attr]
    );
  };

  const handleSubmit = () => {
    if (attributes.length) {
      setStep(4);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg"
    >
      <h2 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">
        Select Attributes for {selectedSite}
      </h2>
      <div className="grid grid-cols-2 gap-4 mb-4">
        {allAttributes.map((attr) => (
          <div key={attr} className="flex items-center">
            <input
              type="checkbox"
              checked={attributes.includes(attr)}
              onChange={() => toggleAttribute(attr)}
              className="mr-2 h-5 w-5 text-blue-600 focus:ring-blue-500"
            />
            <label className="text-gray-700 dark:text-gray-300 capitalize">{attr}</label>
          </div>
        ))}
      </div>
      <button
        onClick={handleSubmit}
        disabled={!attributes.length}
        className="w-full px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-transform transform hover:scale-105"
      >
        Start Scraping
      </button>
    </motion.div>
  );
}