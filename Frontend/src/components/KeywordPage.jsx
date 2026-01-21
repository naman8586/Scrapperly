import { useState, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ChevronLeft, Globe, Loader2, AlertCircle } from 'lucide-react';

const KeywordPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { selectedSite } = location.state || {};
  const [formData, setFormData] = useState({
    keyword: '',
    pageCount: 1,
    retries: 3
  });
  const [errors, setErrors] = useState({});
  const [isLoading, setIsLoading] = useState(false);

  const validateForm = useCallback(() => {
    const newErrors = {};
    if (!formData.keyword.trim()) {
      newErrors.keyword = 'Search keyword is required';
    } else if (formData.keyword.length > 100) {
      newErrors.keyword = 'Keyword must be less than 100 characters';
    }
    if (formData.pageCount < 1 || formData.pageCount > 50) {
      newErrors.pageCount = 'Page count must be between 1 and 50';
    }
    if (formData.retries < 1 || formData.retries > 10) {
      newErrors.retries = 'Retries must be between 1 and 10';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  }, [formData]);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: name === 'pageCount' || name === 'retries' ? parseInt(value) || 1 : value
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    setIsLoading(true);
    setTimeout(() => {
      setIsLoading(false);
      navigate('/fields', { state: { selectedSite, ...formData } });
    }, 1000);
  };

  const handleBack = () => {
    navigate('/');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 px-4">
      <div className="bg-white/10 backdrop-blur-md rounded-3xl shadow-2xl p-8 md:p-12 w-full max-w-2xl border border-white/20">
        <div className="flex items-center mb-8">
          <button
            onClick={handleBack}
            className="mr-4 text-gray-300 hover:text-white transition-colors p-2 rounded-lg hover:bg-white/10"
            aria-label="Go back to platform selection"
          >
            <ChevronLeft className="w-6 h-6" aria-hidden="true" />
          </button>
          <div className="flex-1">
            <h1 className="text-3xl font-bold text-white mb-2">
              Configure Scraping Parameters
            </h1>
            <p className="text-gray-300">
              Set up your search criteria and scraping preferences
            </p>
          </div>
        </div>

        <div className="mb-8 p-4 bg-blue-500/20 border border-blue-500/30 rounded-xl">
          <div className="flex items-center text-blue-200">
            <Globe className="w-5 h-5 mr-2" aria-hidden="true" />
            <span className="font-medium">Selected Platform: {selectedSite || 'N/A'}</span>
          </div>
        </div>

        {errors.keyword || errors.pageCount || errors.retries ? (
          <div className="mb-6 p-4 bg-red-500/20 border border-red-500/30 rounded-xl text-red-200 flex items-center">
            <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0" aria-hidden="true" />
            <span>
              {errors.keyword || errors.pageCount || errors.retries}
            </span>
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label htmlFor="keyword" className="block text-white text-lg font-semibold mb-2">
              Search Keyword
            </label>
            <input
              id="keyword"
              type="text"
              name="keyword"
              value={formData.keyword}
              onChange={handleInputChange}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/20"
              placeholder="Enter search keyword (e.g., Nike Shoes)"
              aria-invalid={!!errors.keyword}
              aria-describedby={errors.keyword ? "keyword-error" : undefined}
            />
            {errors.keyword && (
              <p id="keyword-error" className="text-red-400 text-sm mt-1">{errors.keyword}</p>
            )}
          </div>
          <div>
            <label htmlFor="pageCount" className="block text-white text-lg font-semibold mb-2">
              Number of Pages
            </label>
            <input
              id="pageCount"
              type="number"
              name="pageCount"
              value={formData.pageCount}
              onChange={handleInputChange}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/20"
              min="1"
              max="50"
              aria-invalid={!!errors.pageCount}
              aria-describedby={errors.pageCount ? "pageCount-error" : undefined}
            />
            {errors.pageCount && (
              <p id="pageCount-error" className="text-red-400 text-sm mt-1">{errors.pageCount}</p>
            )}
          </div>
          <div>
            <label htmlFor="retries" className="block text-white text-lg font-semibold mb-2">
              Retry Attempts
            </label>
            <input
              id="retries"
              type="number"
              name="retries"
              value={formData.retries}
              onChange={handleInputChange}
              className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/20"
              min="1"
              max="10"
              aria-invalid={!!errors.retries}
              aria-describedby={errors.retries ? "retries-error" : undefined}
            />
            {errors.retries && (
              <p id="retries-error" className="text-red-400 text-sm mt-1">{errors.retries}</p>
            )}
          </div>
          <div className="flex gap-4">
            <button
              type="button"
              onClick={handleBack}
              className="flex-1 py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-xl transition-all duration-200"
              aria-label="Go back to platform selection"
            >
              Back
            </button>
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 py-3 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
              aria-label="Proceed to field selection"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
                  <span>Processing...</span>
                </>
              ) : (
                <>
                  <span>Next</span>
                  <ChevronLeft className="w-5 h-5 rotate-180" aria-hidden="true" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default KeywordPage;