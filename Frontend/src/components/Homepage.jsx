import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Search, AlertCircle, Loader2 } from 'lucide-react';

// Constants
const PLATFORMS = [
  { label: 'Amazon', value: 'amazon', icon: '🛒' },
  { label: 'Flipkart', value: 'flipkart', icon: '🛍️' },
  { label: 'Alibaba', value: 'alibaba', icon: '🏭' },
  { label: 'DHgate', value: 'dhgate', icon: '📦' },
  { label: 'IndiaMart', value: 'indiamart', icon: '🏪' },
  { label: 'MadeInChina', value: 'madeinchina', icon: '🏭' },
  { label: 'eBay', value: 'ebay', icon: '🛒' },
];

// HomePage Component
const HomePage = () => {
  const navigate = useNavigate();
  const [selectedSite, setSelectedSite] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSiteSelect = (siteValue) => {
    setSelectedSite(siteValue);
    setError('');
  };

  const handleStart = () => {
    if (!selectedSite) {
      setError('Please select an e-commerce platform to continue.');
      return;
    }
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      navigate('/keyword', { state: { selectedSite } });
    }, 1000);
  };

  return (
    <div 
      className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 px-4"
      style={{ backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.1) 0%, rgba(255,255,255,0) 100%)' }}
    >
      <div className="bg-white/10 backdrop-blur-md rounded-3xl shadow-2xl p-8 md:p-12 w-full max-w-2xl border border-white/20">
        <div className="text-center mb-8">
          <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-r from-blue-500 to-purple-600 rounded-2xl flex items-center justify-center">
            <Search className="w-8 h-8 text-white" aria-hidden="true" />
          </div>
          <h1 className="text-4xl font-bold text-white mb-2">
            E-commerce Scraper
          </h1>
          <p className="text-gray-300 text-lg">
            Extract product data from major e-commerce platforms
          </p>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-500/20 border border-red-500/30 rounded-xl text-red-200 flex items-center">
            <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0" aria-hidden="true" />
            <span>{error}</span>
          </div>
        )}

        <div className="mb-8">
          <label className="block text-white text-lg font-semibold mb-4">
            Select E-commerce Platform
          </label>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {PLATFORMS.map((platform) => (
              <button
                key={platform.value}
                onClick={() => handleSiteSelect(platform.value)}
                className={`p-4 rounded-xl border-2 transition-all duration-200 flex items-center space-x-3 ${
                  selectedSite === platform.value
                    ? 'border-blue-400 bg-blue-500/20 text-white'
                    : 'border-gray-600 bg-gray-800/50 text-gray-300 hover:border-gray-500 hover:bg-gray-700/50'
                }`}
                aria-pressed={selectedSite === platform.value}
                aria-label={`Select ${platform.label} platform`}
              >
                <span className="text-2xl" aria-hidden="true">{platform.icon}</span>
                <span className="font-medium">{platform.label}</span>
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleStart}
          disabled={isLoading}
          className="w-full py-4 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
          aria-label="Continue to keyword selection"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
              <span>Initializing...</span>
            </>
          ) : (
            <>
              <span>Continue</span>
              <ChevronLeft className="w-5 h-5 rotate-180" aria-hidden="true" />
            </>
          )}
        </button>
      </div>
    </div>
  );
};

export default HomePage;