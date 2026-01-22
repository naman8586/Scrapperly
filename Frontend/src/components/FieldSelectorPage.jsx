import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ChevronLeft, Settings, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';
import { scraperAPI } from '../services/api'; // Add this import

const SUPPORTED_FIELDS = ['url', 'title', 'exact_price', 'images', 'description', 'seller', 'rating', 'reviews'];

const FieldSelectorPage = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { selectedSite, keyword, pageCount, retries } = location.state || {};
    const [selectedFields, setSelectedFields] = useState(['url', 'title', 'exact_price', 'images']);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');

    // Validate navigation state on mount
    useEffect(() => {
        if (!selectedSite || !keyword) {
            setError('Missing required parameters. Please start over.');
            setTimeout(() => navigate('/'), 3000);
        }
    }, [selectedSite, keyword, navigate]);

    const handleFieldToggle = (field) => {
        setSelectedFields(prev =>
            prev.includes(field)
                ? prev.filter(f => f !== field)
                : [...prev, field]
        );
    };

    const handleSelectAll = () => setSelectedFields([...SUPPORTED_FIELDS]);
    const handleSelectNone = () => setSelectedFields([]);

    const handleSubmit = async () => {
        if (selectedFields.length === 0) {
            setError('Please select at least one field to extract.');
            return;
        }
        
        setIsLoading(true);
        setError('');
        
        try {
            const response = await scraperAPI.scrape({
                site: selectedSite,
                keyword,
                pageCount,
                retries,
                fields: selectedFields.join(',')
            });

            if (response.data.success) {
                navigate('/results', {
                    state: {
                        selectedSite,
                        keyword,
                        scrapedData: response.data.data.products
                    }
                });
            } else {
                setError('Scraping failed. Please try again.');
            }
        } catch (error) {
            console.error('Scraping error:', error);
            const errorMessage = error.response?.data?.message || 'Failed to scrape data. Please try again.';
            setError(errorMessage);
        } finally {
            setIsLoading(false);
        }
    };

    const getFieldIcon = (field) => {
        const icons = {
            url: '🔗',
            title: '📄',
            exact_price: '💰',
            images: '🖼️',
            description: '📝',
            seller: '👤',
            rating: '⭐',
            reviews: '💬'
        };
        return icons[field] || '📋';
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 px-4 py-8">
            <div className="max-w-4xl mx-auto">
                <div className="bg-white/10 backdrop-blur-md rounded-3xl shadow-2xl p-8 md:p-12 border border-white/20">
                    <div className="flex items-center mb-8">
                        <button
                            onClick={() => navigate('/keyword', { state: { selectedSite } })}
                            className="mr-4 text-gray-300 hover:text-white transition-colors p-2 rounded-lg hover:bg-white/10"
                            aria-label="Go back to keyword selection"
                        >
                            <ChevronLeft className="w-6 h-6" />
                        </button>
                        <div className="flex-1">
                            <h1 className="text-3xl font-bold text-white mb-2">
                                Select Data Fields
                            </h1>
                            <p className="text-gray-300">
                                Choose which product information you want to extract
                            </p>
                        </div>
                    </div>

                    {error && (
                        <div className="mb-6 p-4 bg-red-500/20 border border-red-500/30 rounded-xl text-red-200 flex items-center">
                            <AlertCircle className="w-5 h-5 mr-2 flex-shrink-0" />
                            <span>{error}</span>
                        </div>
                    )}

                    <div className="mb-8 p-4 bg-blue-500/20 border border-blue-500/30 rounded-xl">
                        <h2 className="text-white font-semibold mb-2">Scraping Configuration</h2>
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                            <div className="text-gray-300">
                                <span className="font-medium">Platform:</span> {selectedSite || 'N/A'}
                            </div>
                            <div className="text-gray-300">
                                <span className="font-medium">Keyword:</span> {keyword || 'N/A'}
                            </div>
                            <div className="text-gray-300">
                                <span className="font-medium">Pages:</span> {pageCount || 'N/A'}
                            </div>
                            <div className="text-gray-300">
                                <span className="font-medium">Retries:</span> {retries || 'N/A'}
                            </div>
                        </div>
                    </div>

                    <div className="flex justify-between items-center mb-6">
                        <h2 className="text-xl font-semibold text-white">Available Fields</h2>
                        <div className="flex space-x-3">
                            <button
                                onClick={handleSelectAll}
                                className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
                                aria-label="Select all fields"
                            >
                                Select All
                            </button>
                            <button
                                onClick={handleSelectNone}
                                className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-lg font-medium transition-colors"
                                aria-label="Clear all field selections"
                            >
                                Clear All
                            </button>
                        </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
                        {SUPPORTED_FIELDS.map((field) => (
                            <button
                                key={field}
                                onClick={() => handleFieldToggle(field)}
                                className={`p-4 rounded-xl border-2 transition-all duration-200 text-left ${
                                    selectedFields.includes(field)
                                        ? 'border-blue-400 bg-blue-500/20 text-white'
                                        : 'border-gray-600 bg-gray-800/50 text-gray-300 hover:border-gray-500 hover:bg-gray-700/50'
                                }`}
                                aria-pressed={selectedFields.includes(field)}
                                aria-label={`Toggle ${field.replace('_', ' ')} field`}
                            >
                                <div className="flex items-center space-x-3">
                                    <span className="text-2xl">{getFieldIcon(field)}</span>
                                    <div>
                                        <div className="font-medium capitalize">{field.replace('_', ' ')}</div>
                                        {selectedFields.includes(field) && (
                                            <CheckCircle className="w-5 h-5 text-blue-400 mt-1" />
                                        )}
                                    </div>
                                </div>
                            </button>
                        ))}
                    </div>

                    <div className="flex gap-4">
                        <button
                            onClick={() => navigate('/keyword', { state: { selectedSite } })}
                            className="flex-1 py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-xl transition-all duration-200"
                            aria-label="Go back to keyword selection"
                        >
                            Back
                        </button>
                        <button
                            onClick={handleSubmit}
                            disabled={isLoading}
                            className="flex-1 py-3 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                            aria-label="Start scraping with selected fields"
                        >
                            {isLoading ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    <span>Starting Scraper...</span>
                                </>
                            ) : (
                                <>
                                    <span>Start Scraping</span>
                                    <Settings className="w-5 h-5" />
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default FieldSelectorPage;