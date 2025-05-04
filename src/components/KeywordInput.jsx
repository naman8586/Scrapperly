'use client';
import { useState, useContext } from 'react';
import { motion } from 'framer-motion';
import { ScraperContext } from './ScraperContext';

export default function KeywordInput() {
  const { keyword, setKeyword, setStep } = useContext(ScraperContext);
  const [input, setInput] = useState(keyword);

  const handleSubmit = () => {
    if (input.trim()) {
      setKeyword(input.trim());
      setStep(3);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg"
    >
      <h2 className="text-2xl font-bold mb-4 text-gray-900 dark:text-white">
        Enter Keyword
      </h2>
      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g., Christian Dior perfume"
          className="flex-1 p-3 border rounded-lg bg-gray-50 dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500"
        />
        <button
          onClick={handleSubmit}
          disabled={!input.trim()}
          className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition-transform transform hover:scale-105"
        >
          Next
        </button>
      </div>
    </motion.div>
  );
}