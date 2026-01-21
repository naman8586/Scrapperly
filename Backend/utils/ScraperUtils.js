const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const winston = require('winston');
const sanitize = require('sanitize-filename');

// Initialize logger
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

const runScraper = (site, keyword, pageCount, retries, fields) => {
  const scriptPath = path.join(__dirname, '..', 'scrapers', `${sanitize(site)}.py`);

  if (!fs.existsSync(scriptPath)) {
    logger.error({ message: `Scraper script not found for ${site}`, scriptPath });
    throw new Error(`Scraper script not found for ${site}`);
  }

  // Sanitize inputs to prevent command injection
  const safeKeyword = keyword.replace(/"/g, '\\"').replace(/`/g, '\\`');
  const safeFields = fields.replace(/"/g, '\\"').replace(/`/g, '\\`');
  const command = `python "${scriptPath}" "${safeKeyword}" ${pageCount} ${retries} "${safeFields}"`;

  logger.info({ message: `Executing scraper command: ${command}` });

  try {
    const output = execSync(command, {
      encoding: 'utf8',
      stdio: 'pipe',
      maxBuffer: 10 * 1024 * 1024, // 10MB
    });

    logger.info({ message: `Scraper output received for ${site}`, length: output.length });

    try {
      const result = JSON.parse(output);
      return result;
    } catch (parseError) {
      logger.error({
        message: `Failed to parse scraper output for ${site}`,
        error: parseError.message,
        outputSnippet: output.substring(0, 200),
      });
      throw new Error(`Failed to parse scraper output: ${parseError.message}`);
    }
  } catch (error) {
    const errorMessage = error.stderr || error.message || 'Unknown error';
    logger.error({ message: `Error running scraper for ${site}`, error: errorMessage });

    if (errorMessage.includes('CAPTCHA detected')) {
      const captchaTypeMatch = errorMessage.match(/CAPTCHA_TYPE: (\w+)/);
      const captchaUrlMatch = errorMessage.match(/CAPTCHA_URL: (.+?)(\n|$)/);
      return {
        status: 'captcha_required',
        captcha: {
          type: captchaTypeMatch ? captchaTypeMatch[1] : 'unknown',
          url: captchaUrlMatch ? captchaUrlMatch[1] : '',
        },
      };
    }

    throw new Error(`Python script failed: ${errorMessage}`);
  }
};

const validateCaptcha = (site, captchaInput, sessionId) => {
  const scriptPath = path.join(__dirname, '..', 'scrapers', `${sanitize(site)}_captcha.py`);

  if (!fs.existsSync(scriptPath)) {
    logger.error({ message: `CAPTCHA validation script not found for ${site}`, scriptPath });
    throw new Error(`CAPTCHA validation script not found for ${site}`);
  }

  // Sanitize inputs
  const safeCaptchaInput = captchaInput.replace(/"/g, '\\"').replace(/`/g, '\\`');
  const safeSessionId = sessionId.replace(/"/g, '\\"').replace(/`/g, '\\`');
  const command = `python "${scriptPath}" "${safeCaptchaInput}" "${safeSessionId}"`;

  logger.info({ message: `Executing CAPTCHA validation command: ${command}` });

  try {
    const output = execSync(command, {
      encoding: 'utf8',
      stdio: 'pipe',
      maxBuffer: 2 * 1024 * 1024, // 2MB
    });

    logger.info({ message: `CAPTCHA validation output for ${site}`, output });

    try {
      const result = JSON.parse(output);
      return result;
    } catch (parseError) {
      logger.error({
        message: `Failed to parse CAPTCHA validation output for ${site}`,
        error: parseError.message,
        outputSnippet: output.substring(0, 200),
      });
      throw new Error(`Failed to parse CAPTCHA validation output: ${parseError.message}`);
    }
  } catch (error) {
    const errorMessage = error.stderr || error.message || 'Unknown error';
    logger.error({ message: `Error validating CAPTCHA for ${site}`, error: errorMessage });
    throw new Error(`CAPTCHA validation failed: ${errorMessage}`);
  }
};

module.exports = { runScraper, validateCaptcha };