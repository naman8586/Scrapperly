import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomePage from './components/Homepage';
import KeywordPage from './components/KeywordPage';
import FieldSelectorPage from './components/FieldSelectorPage';
import CaptchaPage from './components/CaptchaPage';
import ResultsPage from './components/ResultPage';

const App = () => {
  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/keyword" element={<KeywordPage />} />
          <Route path="/fields" element={<FieldSelectorPage />} />
          <Route path="/captcha" element={<CaptchaPage />} />
          <Route path="/results" element={<ResultsPage />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
};

export default App;