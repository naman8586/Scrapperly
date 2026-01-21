import { useState, useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ChevronLeft, Settings, AlertCircle, CheckCircle, Loader2 } from 'lucide-react';

const SUPPORTED_FIELDS = ['url', 'title', 'exact_price', 'images', 'description', 'seller', 'rating', 'reviews'];

const FieldSelectorPage = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { selectedSite, keyword, pageCount, retries } = location.state || {};
    const [selectedFields, setSelectedFields] = useState(['url', 'title', 'exact_price', 'images']);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState('');
    const [showCaptcha, setShowCaptcha] = useState(false);
    const [captchaData] = useState({ type: 'image', url: 'https://via.placeholder.com/300x100?text=CAPTCHA' });
    const [captchaInput, setCaptchaInput] = useState('');

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

    const generateMockData = () => {
        const mockData = [
            {
                title: `${keyword || 'Product'} 1`,
                images: ['https://via.placeholder.com/150'],
                website_name: selectedSite || 'Unknown',
                url: 'https://example.com/product1',
                exact_price: '99.99',
                description: 'Sample product description',
                seller: 'Sample Seller',
                rating: '4.5',
                reviews: '120'
            },
            {
                title: `${keyword || 'Product'} 2`,
                images: ['https://via.placeholder.com/150'],
                website_name: selectedSite || 'Unknown',
                url: 'https://example.com/product2',
                exact_price: '149.99',
                description: 'Another product description',
                seller: 'Another Seller',
                rating: '4.0',
                reviews: '85'
            }
        ];
        // Filter mock data to include only selected fields
        return mockData.map(item => {
            const filteredItem = {};
            selectedFields.forEach(field => {
                filteredItem[field] = item[field];
            });
            return filteredItem;
        });
    };

    const handleSubmit = () => {
        if (selectedFields.length === 0) {
            setError('Please select at least one field to extract.');
            return;
        }
        setIsLoading(true);
        setError('');
        if (Math.random() < 0.2) {
            setTimeout(() => {
                setShowCaptcha(true);
                setIsLoading(false);
            }, 1000);
        } else {
            setTimeout(() => {
                setIsLoading(false);
                navigate('/results', {
                    state: {
                        selectedSite,
                        keyword,
                        scrapedData: generateMockData()
                    }
                });
            }, 2000);
        }
    };

    const handleCaptchaSubmit = () => {
        if (!captchaInput.trim()) {
            setError('Please enter the CAPTCHA text.');
            return;
        }
        setIsLoading(true);
        setTimeout(() => {
            setShowCaptcha(false);
            setIsLoading(false);
            navigate('/results', {
                state: {
                    selectedSite,
                    keyword,
                    scrapedData: generateMockData()
                }
            });
        }, 1500);
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

                {showCaptcha && (
                    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50" role="dialog" aria-modal="true">
                        <div className="bg-white/10 backdrop-blur-md rounded-2xl shadow-2xl p-8 w-full max-w-md border border-white/20">
                            <h2 className="text-2xl font-bold text-white mb-4 text-center">
                                CAPTCHA Verification
                            </h2>
                            <p className="text-gray-300 mb-6 text-center">
                                Please complete the verification to continue
                            </p>
                            <div className="mb-6">
                                <img
                                    src={captchaData.url}
                                    alt="CAPTCHA verification image"
                                    className="w-full h-32 object-contain bg-gray-800 rounded-lg mb-4"
                                />
                                <input
                                    type="text"
                                    value={captchaInput}
                                    onChange={(e) => setCaptchaInput(e.target.value)}
                                    placeholder="Enter CAPTCHA text"
                                    className="w-full px-4 py-3 bg-gray-800/50 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/20 transition-all"
                                    aria-label="CAPTCHA text input"
                                />
                            </div>
                            <div className="flex gap-4">
                                <button
                                    onClick={() => setShowCaptcha(false)}
                                    className="flex-1 py-3 bg-gray-700 hover:bg-gray-600 text-white font-semibold rounded-xl transition-all duration-200"
                                    aria-label="Cancel CAPTCHA verification"
                                >
                                    Cancel
                                </button>
                                <button
                                    onClick={handleCaptchaSubmit}
                                    disabled={isLoading}
                                    className="flex-1 py-3 bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white font-semibold rounded-xl transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center space-x-2"
                                    aria-label="Submit CAPTCHA verification"
                                >
                                    {isLoading ? (
                                        <>
                                            <Loader2 className="w-5 h-5 animate-spin" />
                                            <span>Verifying...</span>
                                        </>
                                    ) : (
                                        'Verify'
                                    )}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default FieldSelectorPage;