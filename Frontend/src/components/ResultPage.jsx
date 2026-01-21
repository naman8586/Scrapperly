import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Download, XCircle, AlertCircle, CheckCircle, ArrowLeft } from 'lucide-react';

const ResultsPage = () => {
  const [scrapingStatus, setScrapingStatus] = useState('loading');
  const [data, setData] = useState([]);
  const [error, setError] = useState('');
  const [selectedCard, setSelectedCard] = useState(null);
  const location = useLocation();
  const navigate = useNavigate();
  const { selectedSite, keyword, scrapedData } = location.state || {};

  useEffect(() => {
    if (!selectedSite || !keyword) {
      setError('Missing site or keyword. Redirecting to home page...');
      setScrapingStatus('failed');
      setTimeout(() => navigate('/'), 3000);
      return;
    }

    if (scrapedData && Array.isArray(scrapedData)) {
      setData(scrapedData);
      setScrapingStatus('completed');
    } else {
      setError('No valid data received. Showing fallback data.');
      setScrapingStatus('failed');
      setData([
        {
          title: `${keyword || 'Test'} Product`,
          images: ['https://via.placeholder.com/150'],
          website_name: selectedSite || 'Unknown',
          url: 'https://example.com',
          exact_price: '999',
        },
      ]);
    }
  }, [selectedSite, keyword, scrapedData, navigate]);

  const handleDownload = () => {
    const safeKeyword = (keyword || 'products').replace(/[^a-zA-Z0-9\s]/g, '_').replace(/\s+/g, '_');
    const safeSite = (selectedSite || 'unknown').replace(/[^a-zA-Z0-9\s]/g, '_').replace(/\s+/g, '_');
    const jsonString = JSON.stringify(data, null, 2);
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `products_${safeKeyword}_${safeSite}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const renderField = (field, value, isModal = false) => {
    if (!value) return 'N/A';
    if (field === 'images') return value.join(', ');
    if (field === 'feedback') return `Rating: ${value.rating || 'N/A'}, Reviews: ${value.review || 'N/A'}`;
    if (field === 'specifications') return Object.entries(value).map(([k, v]) => `${k}: ${v}`).join(', ');
    if (field === 'image_url' || field === 'url') {
      return (
        <a
          href={value}
          target="_blank"
          rel="noreferrer"
          className={`text-blue-400 hover:text-blue-300 underline block ${
            isModal ? 'whitespace-normal break-words' : 'truncate max-w-full'
          }`}
          aria-label={`Visit ${field} link`}
        >
          {value}
        </a>
      );
    }
    return value.toString();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 p-4 sm:p-8 font-sans">
      <div className="max-w-5xl mx-auto">
        <div className="bg-white/10 backdrop-blur-md rounded-3xl shadow-2xl p-6 sm:p-8 border border-white/20">
          <div className="flex items-center mb-6">
            <button
              onClick={() => navigate('/')}
              className="mr-4 text-gray-300 hover:text-white transition-colors p-2 rounded-lg hover:bg-white/10"
              aria-label="Go back to home page"
            >
              <ArrowLeft className="w-6 h-6" aria-hidden="true" />
            </button>
            <div className="flex-1">
              <h1 className="text-3xl font-bold text-white text-center sm:text-left">Scraping Results</h1>
              <p className="text-gray-300 text-center sm:text-left mt-2">
                Site: {selectedSite || 'N/A'} | Keyword: {keyword || 'N/A'} | Items: {data.length}
              </p>
            </div>
          </div>

          {error && (
            <div
              className="mb-6 p-4 bg-red-500/20 border border-red-500/30 rounded-xl text-red-200 flex items-center"
              role="alert"
              id="error-message"
            >
              <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0" aria-hidden="true" />
              <span>{error}</span>
            </div>
          )}
          {scrapingStatus === 'loading' && (
            <div className="mb-6 text-center text-gray-300 flex items-center justify-center">
              <svg
                className="animate-spin h-5 w-5 mr-2 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                ></circle>
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                ></path>
              </svg>
              Loading results...
            </div>
          )}

          {(scrapingStatus === 'completed' || scrapingStatus === 'failed') && (
            <>
              <div
                className={`mb-6 p-4 rounded-xl border ${
                  scrapingStatus === 'completed'
                    ? 'bg-green-500/20 border-green-500/30'
                    : 'bg-red-500/20 border-red-500/30'
                }`}
              >
                <div className="flex items-center justify-center mb-2">
                  <CheckCircle
                    className={`w-6 h-6 ${
                      scrapingStatus === 'completed' ? 'text-green-400' : 'text-red-400'
                    } mr-2`}
                    aria-hidden="true"
                  />
                  <p
                    className={`font-medium ${
                      scrapingStatus === 'completed' ? 'text-green-400' : 'text-red-400'
                    }`}
                  >
                    {scrapingStatus === 'completed' ? 'Scraping completed successfully!' : 'Scraping failed'}
                  </p>
                </div>
                <p className="text-center text-gray-300">
                  {scrapingStatus === 'completed'
                    ? `Found ${data.length} items`
                    : 'Showing fallback data due to failure'}
                </p>
              </div>

              <button
                onClick={handleDownload}
                className="mb-6 w-full py-3 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold rounded-xl transition-all duration-200 flex items-center justify-center space-x-2"
                aria-label="Download results as JSON"
              >
                <Download className="w-5 h-5" aria-hidden="true" />
                <span>Download JSON</span>
              </button>

              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
                {data.map((item, index) => (
                  <div
                    key={index}
                    className="bg-white/10 backdrop-blur-md p-4 rounded-xl shadow-lg border border-white/20 hover:shadow-xl hover:-translate-y-1 transition-all duration-200 cursor-pointer"
                    onClick={() => setSelectedCard(item)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        setSelectedCard(item);
                      }
                    }}
                    aria-label={`View details for ${item.title || 'product'}`}
                  >
                    {item.images && item.images[0] && (
                      <img
                        src={item.images[0]}
                        alt={item.title || 'Product'}
                        className="w-full h-48 object-cover rounded-lg mb-4"
                        onError={(e) => (e.target.src = 'https://via.placeholder.com/150')}
                      />
                    )}
                    {Object.entries(item).map(([field, value]) => (
                      field !== 'images' && (
                        <p key={field} className="text-gray-300 mb-2 truncate">
                          <span className="font-semibold capitalize">{field.replace('_', ' ')}:</span>{' '}
                          {renderField(field, value)}
                        </p>
                      )
                    ))}
                  </div>
                ))}
              </div>

              <button
                onClick={() => navigate('/')}
                className="mt-6 w-full py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-xl transition-all duration-200 flex items-center justify-center space-x-2"
                aria-label="Start a new search"
              >
                <ArrowLeft className="w-5 h-5" aria-hidden="true" />
                <span>New Search</span>
              </button>
            </>
          )}
        </div>

        {selectedCard && (
          <div
            className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4 sm:p-6"
            onClick={() => setSelectedCard(null)}
            role="dialog"
            aria-modal="true"
            aria-label="Product details modal"
          >
            <div
              className="bg-white/10 backdrop-blur-md max-w-2xl w-full p-6 sm:p-8 rounded-2xl shadow-2xl border border-white/20 relative animate-scaleIn overflow-y-auto max-h-[90vh]"
              onClick={(e) => e.stopPropagation()}
            >
              <button
                className="absolute top-3 right-3 text-gray-300 hover:text-red-400 transition-colors"
                onClick={() => setSelectedCard(null)}
                aria-label="Close product details modal"
              >
                <XCircle className="w-6 h-6" aria-hidden="true" />
              </button>
              {selectedCard.images && selectedCard.images[0] && (
                <img
                  src={selectedCard.images[0]}
                  alt={selectedCard.title || 'Product'}
                  className="w-full h-64 object-cover rounded-lg mb-4"
                  onError={(e) => (e.target.src = 'https://via.placeholder.com/150')}
                />
              )}
              {Object.entries(selectedCard).map(([field, value]) => (
                field !== 'images' && (
                  <p key={field} className="text-gray-300 mb-3">
                    <span className="font-semibold capitalize">{field.replace('_', ' ')}:</span>{' '}
                    {renderField(field, value, true)}
                  </p>
                )
              ))}
            </div>
          </div>
        )}
      </div>

      <style>{`
        .animate-scaleIn {
          animation: scaleIn 0.3s ease-out forwards;
        }

        @keyframes scaleIn {
          0% { transform: scale(0.7); opacity: 0; }
          100% { transform: scale(1); opacity: 1; }
        }
      `}</style>
    </div>
  );
};

export default ResultsPage;