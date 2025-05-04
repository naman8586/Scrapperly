'use client';
import { useState, useContext } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Toaster } from 'react-hot-toast';
import SiteSelector from './components/SiteSelector';
import KeywordInput from './components/KeywordInput';
import AttributeSelector from './components/AttributeSelector';
import ResultsDisplay from './components/ResultsDisplay';
import { ScraperContext, ScraperProvider } from './components/ScraperContext';
import { ThemeProvider } from './components/ThemeProvider';

const Home = () => {
  const { step, setStep } = useContext(ScraperContext);

  return (
    <ThemeProvider>
      <div className="min-h-screen bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-900 transition-colors">
        <Toaster position="top-right" />
        <AnimatePresence mode="wait">
          {step === 0 && (
            <motion.div
              key="splash"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.5 }}
              className="flex items-center justify-center min-h-screen"
            >
              <div className="text-center p-8 bg-white dark:bg-gray-800 rounded-xl shadow-2xl">
                <h1 className="text-4xl font-extrabold mb-4 text-gray-900 dark:text-white">
                  Scraper Pro
                </h1>
                <p className="text-lg mb-6 text-gray-600 dark:text-gray-300">
                  Unleash the power of e-commerce scraping
                </p>
                <button
                  onClick={() => setStep(1)}
                  className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-transform transform hover:scale-105"
                >
                  Let's Go
                </button>
              </div>
            </motion.div>
          )}
          {step === 1 && (
            <motion.div
              key="site"
              initial={{ opacity: 0, x: 100 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -100 }}
              transition={{ duration: 0.3 }}
              className="p-8 max-w-2xl mx-auto"
            >
              <SiteSelector />
            </motion.div>
          )}
          {step === 2 && (
            <motion.div
              key="keyword"
              initial={{ opacity: 0, x: 100 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -100 }}
              transition={{ duration: 0.3 }}
              className="p-8 max-w-2xl mx-auto"
            >
              <KeywordInput />
            </motion.div>
          )}
          {step === 3 && (
            <motion.div
              key="attributes"
              initial={{ opacity: 0, x: 100 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -100 }}
              transition={{ duration: 0.3 }}
              className="p-8 max-w-2xl mx-auto"
            >
              <AttributeSelector />
            </motion.div>
          )}
          {step === 4 && (
            <motion.div
              key="results"
              initial={{ opacity: 0, x: 100 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -100 }}
              transition={{ duration: 0.3 }}
              className="p-8 max-w-4xl mx-auto"
            >
              <ResultsDisplay />
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </ThemeProvider>
  );
};

export default function App() {
  return (
    <ScraperProvider>
      <Home />
    </ScraperProvider>
  );
}