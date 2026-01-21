import React, { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';

function CaptchaPage() {
    const [captchaValue, setCaptchaValue] = useState('');
    const [selectedImages, setSelectedImages] = useState([]);
    const [puzzleOrder, setPuzzleOrder] = useState([]);
    const [dropdownValue, setDropdownValue] = useState('');
    const [sliderPosition, setSliderPosition] = useState(0);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const location = useLocation();
    const navigate = useNavigate();
    const { selectedSite, keyword, pageCount, retries, selectedFields } = location.state || {};

    useEffect(() => {
        if (!selectedSite || !keyword || !selectedFields) {
            navigate('/');
        }
    }, [selectedSite, keyword, selectedFields, navigate]);

    // CAPTCHA configurations
    const captchaConfigs = {
        alibaba: {
            type: 'swipe',
            label: 'Slide to verify',
            validate: () => sliderPosition >= 90,
            render: () => (
                <div className="mb-4">
                    <p className="text-gray-300 mb-2">Slide the bar to the right to complete the CAPTCHA.</p>
                    <div className="relative w-full h-12 bg-gray-700 rounded-lg">
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={sliderPosition}
                            onChange={(e) => setSliderPosition(Number(e.target.value))}
                            className="w-full h-12 opacity-0 absolute z-10 cursor-pointer"
                        />
                        <div
                            className="absolute top-0 left-0 h-12 bg-indigo-500 rounded-lg transition-all duration-200"
                            style={{ width: `${sliderPosition}%` }}
                        ></div>
                        <div className="absolute top-0 left-0 w-full h-12 flex items-center justify-center text-white">
                            {sliderPosition >= 90 ? '✓ Verified' : 'Slide to Verify'}
                        </div>
                    </div>
                </div>
            ),
        },
        flipkart: {
            type: 'text',
            label: 'Enter the text shown',
            validate: () => captchaValue.trim().length > 0,
            render: () => (
                <div className="mb-4">
                    <div className="bg-gray-700 p-4 rounded-lg text-gray-300 mb-4">[Mock CAPTCHA Image]</div>
                    <input
                        type="text"
                        value={captchaValue}
                        onChange={(e) => setCaptchaValue(e.target.value)}
                        className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        placeholder="Enter CAPTCHA text (e.g., 12345)"
                    />
                </div>
            ),
        },
        amazon: {
            type: 'click',
            label: 'Select the correct images',
            validate: () => selectedImages.includes('correct'),
            render: () => (
                <div className="mb-4">
                    <p className="text-gray-300 mb-2">Select the image with a checkmark.</p>
                    <div className="grid grid-cols-2 gap-2">
                        {['correct', 'wrong1', 'wrong2', 'wrong3'].map((id) => (
                            <label key={id} className="flex items-center">
                                <input
                                    type="checkbox"
                                    checked={selectedImages.includes(id)}
                                    onChange={() => {
                                        setSelectedImages((prev) =>
                                            prev.includes(id)
                                                ? prev.filter((i) => i !== id)
                                                : [...prev, id]
                                        );
                                    }}
                                    className="mr-2"
                                />
                                <div className="w-16 h-16 bg-gray-700 rounded-lg flex items-center justify-center">
                                    {id === 'correct' ? '✓' : 'X'}
                                </div>
                            </label>
                        ))}
                    </div>
                </div>
            ),
        },
        dhgate: {
            type: 'puzzle',
            label: 'Arrange the puzzle pieces',
            validate: () => puzzleOrder.join(',') === '1,2,3',
            render: () => (
                <div className="mb-4">
                    <p className="text-gray-300 mb-2">Click buttons to arrange pieces in order (1, 2, 3).</p>
                    <div className="flex space-x-2">
                        {[1, 2, 3].map((num) => (
                            <button
                                key={num}
                                onClick={() => {
                                    setPuzzleOrder((prev) =>
                                        prev.includes(num) ? prev : [...prev, num]
                                    );
                                }}
                                className="px-4 py-2 bg-gray-700 text-white rounded-lg"
                                disabled={puzzleOrder.includes(num)}
                            >
                                Piece {num}
                            </button>
                        ))}
                    </div>
                    <p className="text-gray-300 mt-2">Current order: {puzzleOrder.join(', ') || 'None'}</p>
                </div>
            ),
        },
        indiamart: {
            type: 'audio',
            label: 'Enter the audio text',
            validate: () => captchaValue.trim().length > 0,
            render: () => (
                <div className="mb-4">
                    <p className="text-gray-300 mb-2">[Mock Audio: Type "audio123"]</p>
                    <input
                        type="text"
                        value={captchaValue}
                        onChange={(e) => setCaptchaValue(e.target.value)}
                        className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        placeholder="Enter audio text (e.g., audio123)"
                    />
                </div>
            ),
        },
        madeinchina: {
            type: 'math',
            label: 'Solve the math problem',
            validate: () => captchaValue.trim() === '8',
            render: () => (
                <div className="mb-4">
                    <p className="text-gray-300 mb-2">What is 5 + 3?</p>
                    <input
                        type="text"
                        value={captchaValue}
                        onChange={(e) => setCaptchaValue(e.target.value)}
                        className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                        placeholder="Enter answer (e.g., 8)"
                    />
                </div>
            ),
        },
        ebay: {
            type: 'dropdown',
            label: 'Select the correct option',
            validate: () => dropdownValue === 'correct',
            render: () => (
                <div className="mb-4">
                    <p className="text-gray-300 mb-2">Select the option labeled "Correct".</p>
                    <select
                        value={dropdownValue}
                        onChange={(e) => setDropdownValue(e.target.value)}
                        className="w-full p-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                        <option value="" disabled>Select an option</option>
                        <option value="correct">Correct</option>
                        <option value="wrong1">Wrong 1</option>
                        <option value="wrong2">Wrong 2</option>
                    </select>
                </div>
            ),
        },
    };

    const captcha = captchaConfigs[selectedSite] || captchaConfigs.flipkart; // Fallback to Flipkart's text CAPTCHA

    const handleSubmit = async () => {
        if (!captcha.validate()) {
            setError(`Please complete the ${captcha.type} CAPTCHA correctly.`);
            return;
        }
        if (!selectedFields || !Array.isArray(selectedFields)) {
            setError('No fields selected. Please go back and select fields.');
            return;
        }
        setLoading(true);
        setError('');
        try {
            const response = await axios.post('http://localhost:5000/api/scrape', {
                site: selectedSite,
                keyword,
                pageCount,
                retries,
                fields: selectedFields.join(','),
            });
            if (response.data.message?.includes('completed')) {
                navigate('/results', {
                    state: { selectedSite, keyword, scrapedData: response.data.products },
                });
            } else {
                console.error('Scrape failed:', response.data);
                setError(response.data.message || 'Failed to scrape after CAPTCHA. Please try again.');
            }
        } catch (error) {
            console.error('Scrape error:', error);
            const errorMessage = error.response?.data?.message || 'Failed to verify CAPTCHA. Please try again.';
            setError(errorMessage);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center p-4 bg-gray-900">
            <div className="bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-md">
                <h1 className="text-2xl font-bold mb-6 text-center text-indigo-400">
                    CAPTCHA Verification
                </h1>
                {error && (
                    <div className="mb-4 p-3 bg-red-600 text-white rounded-lg">{error}</div>
                )}
                <div className="mb-6">
                    <p className="text-gray-300 mb-4">
                        A CAPTCHA verification is required for {selectedSite}.
                    </p>
                    {captcha.render()}
                    <div className="flex space-x-3 mt-4">
                        <button
                            onClick={() =>
                                navigate('/fields', {
                                    state: { selectedSite, keyword, pageCount, retries },
                                })
                            }
                            className="flex-1 bg-gray-600 hover:bg-gray-700 text-white font-bold py-3 px-4 rounded-lg transition duration-300"
                            disabled={loading}
                        >
                            Back
                        </button>
                        <button
                            onClick={handleSubmit}
                            className="flex-1 bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-3 px-4 rounded-lg transition duration-300"
                            disabled={loading}
                        >
                            {loading ? 'Verifying...' : 'Submit'}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default CaptchaPage;