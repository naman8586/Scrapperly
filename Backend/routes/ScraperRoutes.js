const express = require('express');
const { runScraper, validateCaptcha } = require('../utils/ScraperUtils');
const winston = require('winston');

const router = express.Router();

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
      filename: 'logs/scraper.log',
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 3,
    }),
  ],
});

const ALLOWED_SITES = process.env.ALLOWED_SITES
  ? process.env.ALLOWED_SITES.split(',').map((s) => s.trim().toLowerCase())
  : [];

router.post('/scrape', async (req, res) => {
  const { site, keyword, pageCount, retries, fields } = req.body;

  if (!site || !keyword || !pageCount || !retries || !fields) {
    logger.warn({
      message: 'Missing required parameters in /api/scrape',
      details: { site, keyword, pageCount, retries, fields },
    });
    return res.status(400).json({
      message: 'Missing required parameters',
      details: { site, keyword, pageCount, retries, fields },
    });
  }

  if (!ALLOWED_SITES.includes(site.toLowerCase())) {
    logger.warn({ message: `Invalid site: ${site}`, allowedSites: ALLOWED_SITES });
    return res.status(400).json({
      message: `Invalid site: ${site}. Allowed sites: ${ALLOWED_SITES.join(', ')}`,
    });
  }

  const pageCountNum = parseInt(pageCount, 10);
  const retriesNum = parseInt(retries, 10);
  if (isNaN(pageCountNum) || pageCountNum < 1 || isNaN(retriesNum) || retriesNum < 0) {
    logger.warn({
      message: 'Invalid pageCount or retries',
      details: { pageCount, retries },
    });
    return res.status(400).json({
      message: 'pageCount and retries must be valid positive integers',
    });
  }

  try {
    const result = await runScraper(site, keyword, pageCountNum, retriesNum, fields);
    if (result.status === 'captcha_required') {
      logger.info({ message: `CAPTCHA required for ${site}`, captcha: result.captcha });
      return res.status(200).json({
        message: 'CAPTCHA required',
        captcha: result.captcha,
        sessionId: `${site}_${Date.now()}`,
      });
    }
    logger.info({ message: `Scraping completed for ${site}`, productCount: result.products?.length });
    res.status(200).json({
      message: 'Scraping completed successfully',
      products: result.products || [],
    });
  } catch (error) {
    logger.error({
      message: `Failed to scrape ${site}`,
      error: error.message,
      stack: error.stack,
    });
    res.status(500).json({
      message: `Failed to scrape ${site}`,
      error: error.message,
    });
  }
});

router.post('/captcha', async (req, res) => {
  const { site, captchaInput, sessionId } = req.body;

  if (!site || !captchaInput || !sessionId) {
    logger.warn({
      message: 'Missing required parameters in /api/captcha',
      details: { site, captchaInput, sessionId },
    });
    return res.status(400).json({
      message: 'Missing required parameters',
      details: { site, captchaInput, sessionId },
    });
  }

  if (!ALLOWED_SITES.includes(site.toLowerCase())) {
    logger.warn({ message: `Invalid site for CAPTCHA: ${site}`, allowedSites: ALLOWED_SITES });
    return res.status(400).json({
      message: `Invalid site: ${site}. Allowed sites: ${ALLOWED_SITES.join(', ')}`,
    });
  }

  try {
    const result = await validateCaptcha(site, captchaInput, sessionId);
    if (result.valid) {
      logger.info({ message: `CAPTCHA validated successfully for ${site}` });
      res.status(200).json({ message: 'CAPTCHA validated successfully' });
    } else {
      logger.warn({ message: `Invalid CAPTCHA for ${site}`, result });
      res.status(400).json({ message: result.message || 'Invalid CAPTCHA' });
    }
  } catch (error) {
    logger.error({
      message: `Failed to validate CAPTCHA for ${site}`,
      error: error.message,
      stack: error.stack,
    });
    res.status(500).json({
      message: 'Failed to validate CAPTCHA',
      error: error.message,
    });
  }
});

module.exports = router;