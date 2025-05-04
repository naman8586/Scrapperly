'use client';
import { useState, useEffect, useContext } from 'react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import { ScraperContext } from './ScraperContext';
import { CSVLink } from 'react-csv';

export default function ResultsDisplay() {
  const { selectedSite, keyword, attributes, results, setResults } = useContext(ScraperContext);
  const [loading, setLoading] = useState(true);
  const [sortField, setSortField] = useState('');
  const [sortOrder, setSortOrder] = useState('asc');

  useEffect(() => {
    const fetchResults = async () => {
      setLoading(true);
      try {
        const response = await fetch('/api/scrape', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ website: selectedSite, keyword, attributes }),
        });
        if (!response.ok) throw new Error('Scraping failed');
        const data = await response.json();
        setResults(data);
        toast.success('Scraping completed!');
      } catch (error) {
        toast.error('Error: ' + error.message);
      } finally {
        setLoading(false);
      }
    };
    fetchResults();
  }, [selectedSite, keyword, attributes, setResults]);

  const handleSort = (field) => {
    const newOrder = sortField === field && sortOrder === 'asc' ? 'desc' : 'asc';
    setSortField(field);
    setSortOrder(newOrder);
    setResults((prev) =>
      [...prev].sort((a, b) => {
        const valA = a[field] || 'Unknown';
        const valB = b[field] || 'Unknown';
        if (valA === 'Unknown') return 1;
        if (valB === 'Unknown') return -1;
        return newOrder === 'asc'
          ? valA.localeCompare(valB)
          : valB.localeCompare(valA);
      })
    );
  };

  if (loading) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex items-center justify-center min-h-screen"
      >
        <div className="text-center">
          <div className="animate-spin rounded-full h-16 w-16 border-t-4 border-blue-600"></div>
          <p className="mt-4 text-gray-600 dark:text-gray-300">Scraping in progress...</p>
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="bg-white dark:bg-gray-800 p-6 rounded-xl shadow-lg"
    >
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
          Scraping Results for "{keyword}" on {selectedSite}
        </h2>
        {results.length > 0 && (
          <CSVLink
            data={results}
            filename={`${selectedSite}_${keyword}_results.csv`}
            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
          >
            Export to CSV
          </CSVLink>
        )}
      </div>
      {results.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse">
            <thead>
              <tr>
                {attributes.map((attr) => (
                  <th
                    key={attr}
                    onClick={() => handleSort(attr)}
                    className="border p-3 text-left cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
                  >
                    {attr} {sortField === attr && (sortOrder === 'asc' ? '↑' : '↓')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {results.map((item, index) => (
                <tr key={index} className="hover:bg-gray-50 dark:hover:bg-gray-700">
                  {attributes.map((attr) => (
                    <td key={attr} className="border p-3">
                      {item[attr] === 'Unknown' ? (
                        <span className="text-gray-400">Unknown</span>
                      ) : attr === 'image' ? (
                        <img
                          src={item[attr]}
                          alt="Product"
                          className="h-16 w-16 object-cover rounded"
                          onError={(e) => (e.target.src = '/placeholder.png')}
                        />
                      ) : (
                        item[attr]
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-gray-600 dark:text-gray-300">No results found.</p>
      )}
    </motion.div>
  );
}