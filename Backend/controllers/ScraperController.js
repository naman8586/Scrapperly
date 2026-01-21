const { runScraper } = require('../utils/ScraperUtils');
const winston = require('winston');
const path = require('path');

// Logger setup
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.json()
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({
      filename: path.join(__dirname, '..', 'logs', 'scraper.log'),
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 3,
    }),
  ],
});

exports.runScrapers = async (req, res) => {
  const { keyword, sites, pageCount = '1', retries = '3', fields } = req.body;

  // Validate inputs
  if (!keyword || !Array.isArray(sites) || sites.length === 0 || !fields) {
    logger.warn({
      message: 'Missing or invalid parameters in /api/scrape-multi',
      details: { keyword, sites, pageCount, retries, fields },
    });
    return res.status(400).json({
      message: 'Missing or invalid keyword, sites array, or fields',
      details: { keyword, sites, pageCount, retries, fields },
    });
  }

  const ALLOWED_SITES = process.env.ALLOWED_SITES
    ? process.env.ALLOWED_SITES.split(',').map((s) => s.trim().toLowerCase())
    : [];

  // Validate sites
  const invalidSites = sites.filter((site) => !ALLOWED_SITES.includes(site.toLowerCase()));
  if (invalidSites.length > 0) {
    logger.warn({
      message: `Invalid sites in /api/scrape-multi: ${invalidSites.join(', ')}`,
      allowedSites: ALLOWED_SITES,
    });
    return res.status(400).json({
      message: `Invalid sites: ${invalidSites.join(', ')}. Available sites: ${ALLOWED_SITES.join(', ')}`,
    });
  }

  // Validate numeric inputs
  const pageCountNum = parseInt(pageCount, 10);
  const retriesNum = parseInt(retries, 10);
  if (isNaN(pageCountNum) || pageCountNum < 1 || isNaN(retriesNum) || retriesNum < 0) {
    logger.warn({
      message: 'Invalid pageCount or retries in /api/scrape-multi',
      details: { pageCount, retries },
    });
    return res.status(400).json({
      message: 'pageCount and retries must be positive integers',
    });
  }

  try {
    // Run all scrapers concurrently
    const scraperPromises = sites.map((site) =>
      runScraper(site, keyword, pageCountNum, retriesNum, fields)
        .then((result) => ({
          site,
          status: result.status === 'captcha_required' ? 'captcha_required' : 'success',
          ...result,
        }))
        .catch((error) => ({
          site,
          status: 'error',
          error: error.message,
        }))
    );

    const results = await Promise.all(scraperPromises);

    // Format the results
    const formattedResults = {};
    results.forEach((result) => {
      formattedResults[result.site] = {
        status: result.status,
        ...(result.status === 'success'
          ? { message: 'Scraping completed successfully', products: result.products || [] }
          : result.status === 'captcha_required'
          ? {
              message: 'CAPTCHA required',
              captcha: result.captcha,
              sessionId: `${result.site}_${Date.now()}`,
            }
          : { message: 'Scraping failed', error: result.error }),
      };
    });

    logger.info({
      message: 'Multi-site scraping completed',
      results: Object.keys(formattedResults).map((site) => ({
        site,
        status: formattedResults[site].status,
        productCount: formattedResults[site].products?.length || 0,
      })),
    });

    res.json({
      message: 'Multi-site scraping completed',
      results: formattedResults,
    });
  } catch (err) {
    logger.error({
      message: 'Unexpected error in /api/scrape-multi',
      error: err.message,
      stack: err.stack,
    });
    res.status(500).json({
      message: 'Unexpected error while scraping multiple sites',
      error: err.message,
    });
  }
};