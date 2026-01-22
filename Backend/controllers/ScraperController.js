// const { runScraper } = require('../utils/ScraperUtils');
// const winston = require('winston');
// const path = require('path');

// // Logger setup
// const logger = winston.createLogger({
//   level: 'info',
//   format: winston.format.combine(
//     winston.format.timestamp(),
//     winston.format.json()
//   ),
//   transports: [
//     new winston.transports.Console(),
//     new winston.transports.File({
//       filename: path.join(__dirname, '..', 'logs', 'scraper.log'),
//       maxsize: 10 * 1024 * 1024, // 10MB
//       maxFiles: 3,
//     }),
//   ],
// });

// exports.runScrapers = async (req, res) => {
//   const { keyword, sites, pageCount = '1', retries = '3', fields } = req.body;

//   // Validate inputs
//   if (!keyword || !Array.isArray(sites) || sites.length === 0 || !fields) {
//     logger.warn({
//       message: 'Missing or invalid parameters in /api/scrape-multi',
//       details: { keyword, sites, pageCount, retries, fields },
//     });
//     return res.status(400).json({
//       message: 'Missing or invalid keyword, sites array, or fields',
//       details: { keyword, sites, pageCount, retries, fields },
//     });
//   }

//   const ALLOWED_SITES = process.env.ALLOWED_SITES
//     ? process.env.ALLOWED_SITES.split(',').map((s) => s.trim().toLowerCase())
//     : [];

//   // Validate sites
//   const invalidSites = sites.filter((site) => !ALLOWED_SITES.includes(site.toLowerCase()));
//   if (invalidSites.length > 0) {
//     logger.warn({
//       message: `Invalid sites in /api/scrape-multi: ${invalidSites.join(', ')}`,
//       allowedSites: ALLOWED_SITES,
//     });
//     return res.status(400).json({
//       message: `Invalid sites: ${invalidSites.join(', ')}. Available sites: ${ALLOWED_SITES.join(', ')}`,
//     });
//   }

//   // Validate numeric inputs
//   const pageCountNum = parseInt(pageCount, 10);
//   const retriesNum = parseInt(retries, 10);
//   if (isNaN(pageCountNum) || pageCountNum < 1 || isNaN(retriesNum) || retriesNum < 0) {
//     logger.warn({
//       message: 'Invalid pageCount or retries in /api/scrape-multi',
//       details: { pageCount, retries },
//     });
//     return res.status(400).json({
//       message: 'pageCount and retries must be positive integers',
//     });
//   }

//   try {
//     // Run all scrapers concurrently
//     const scraperPromises = sites.map((site) =>
//       runScraper(site, keyword, pageCountNum, retriesNum, fields)
//         .then((result) => ({
//           site,
//           status: result.status === 'captcha_required' ? 'captcha_required' : 'success',
//           ...result,
//         }))
//         .catch((error) => ({
//           site,
//           status: 'error',
//           error: error.message,
//         }))
//     );

//     const results = await Promise.all(scraperPromises);

//     // Format the results
//     const formattedResults = {};
//     results.forEach((result) => {
//       formattedResults[result.site] = {
//         status: result.status,
//         ...(result.status === 'success'
//           ? { message: 'Scraping completed successfully', products: result.products || [] }
//           : result.status === 'captcha_required'
//           ? {
//               message: 'CAPTCHA required',
//               captcha: result.captcha,
//               sessionId: `${result.site}_${Date.now()}`,
//             }
//           : { message: 'Scraping failed', error: result.error }),
//       };
//     });

//     logger.info({
//       message: 'Multi-site scraping completed',
//       results: Object.keys(formattedResults).map((site) => ({
//         site,
//         status: formattedResults[site].status,
//         productCount: formattedResults[site].products?.length || 0,
//       })),
//     });

//     res.json({
//       message: 'Multi-site scraping completed',
//       results: formattedResults,
//     });
//   } catch (err) {
//     logger.error({
//       message: 'Unexpected error in /api/scrape-multi',
//       error: err.message,
//       stack: err.stack,
//     });
//     res.status(500).json({
//       message: 'Unexpected error while scraping multiple sites',
//       error: err.message,
//     });
//   }
// };


const ScraperJob = require('../models/ScraperJob');
const ScraperResult = require('../models/ScraperResult');
const logger = require('../utils/logger');
const path = require('path');
const fs = require('fs').promises;

// Import scraper modules dynamically
const getScraperModule = (site) => {
  try {
    return require(`../scrapers/${site}.py`);
  } catch (error) {
    logger.warn(`Scraper module not found for ${site}`);
    return null;
  }
};

/**
 * @desc    Create new scraper job
 * @route   POST /api/scraper/jobs
 * @access  Private
 */
const createJob = async (req, res, next) => {
  try {
    const { site, searchQuery, selectedFields, config } = req.body;

    // Check concurrent jobs limit
    const runningJobs = await ScraperJob.countDocuments({
      user: req.user._id,
      status: { $in: ['pending', 'running'] }
    });

    const maxConcurrent = parseInt(process.env.MAX_CONCURRENT_SCRAPERS) || 3;

    if (runningJobs >= maxConcurrent) {
      return res.status(429).json({
        success: false,
        message: `Maximum ${maxConcurrent} concurrent scraping jobs allowed`
      });
    }

    // Create job
    const job = await ScraperJob.create({
      user: req.user._id,
      site,
      searchQuery,
      selectedFields,
      config: config || {}
    });

    logger.info(`Scraper job created: ${job._id} for user ${req.user.email}`);

    // Start scraping in background
    startScraping(job);

    res.status(201).json({
      success: true,
      data: job
    });
  } catch (error) {
    next(error);
  }
};

/**
 * @desc    Get all user jobs
 * @route   GET /api/scraper/jobs
 * @access  Private
 */
const getJobs = async (req, res, next) => {
  try {
    const { status, site, page = 1, limit = 10 } = req.query;

    const query = { user: req.user._id };

    if (status) query.status = status;
    if (site) query.site = site;

    const jobs = await ScraperJob.find(query)
      .sort({ createdAt: -1 })
      .limit(limit * 1)
      .skip((page - 1) * limit);

    const count = await ScraperJob.countDocuments(query);

    res.json({
      success: true,
      data: jobs,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total: count,
        pages: Math.ceil(count / limit)
      }
    });
  } catch (error) {
    next(error);
  }
};

/**
 * @desc    Get job by ID
 * @route   GET /api/scraper/jobs/:id
 * @access  Private
 */
const getJobById = async (req, res, next) => {
  try {
    const job = await ScraperJob.findOne({
      _id: req.params.id,
      user: req.user._id
    });

    if (!job) {
      return res.status(404).json({
        success: false,
        message: 'Job not found'
      });
    }

    res.json({
      success: true,
      data: job
    });
  } catch (error) {
    next(error);
  }
};

/**
 * @desc    Get job results
 * @route   GET /api/scraper/jobs/:id/results
 * @access  Private
 */
const getJobResults = async (req, res, next) => {
  try {
    const { page = 1, limit = 50 } = req.query;

    const job = await ScraperJob.findOne({
      _id: req.params.id,
      user: req.user._id
    });

    if (!job) {
      return res.status(404).json({
        success: false,
        message: 'Job not found'
      });
    }

    const results = await ScraperResult.find({ job: job._id })
      .sort({ 'metadata.itemIndex': 1 })
      .limit(limit * 1)
      .skip((page - 1) * limit);

    const count = await ScraperResult.countDocuments({ job: job._id });

    res.json({
      success: true,
      data: results,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total: count,
        pages: Math.ceil(count / limit)
      }
    });
  } catch (error) {
    next(error);
  }
};

/**
 * @desc    Cancel job
 * @route   PUT /api/scraper/jobs/:id/cancel
 * @access  Private
 */
const cancelJob = async (req, res, next) => {
  try {
    const job = await ScraperJob.findOne({
      _id: req.params.id,
      user: req.user._id
    });

    if (!job) {
      return res.status(404).json({
        success: false,
        message: 'Job not found'
      });
    }

    if (job.status === 'completed' || job.status === 'failed') {
      return res.status(400).json({
        success: false,
        message: 'Cannot cancel completed or failed job'
      });
    }

    job.status = 'cancelled';
    job.completedAt = Date.now();
    await job.save();

    logger.info(`Job cancelled: ${job._id}`);

    res.json({
      success: true,
      data: job
    });
  } catch (error) {
    next(error);
  }
};

/**
 * @desc    Delete job and its results
 * @route   DELETE /api/scraper/jobs/:id
 * @access  Private
 */
const deleteJob = async (req, res, next) => {
  try {
    const job = await ScraperJob.findOne({
      _id: req.params.id,
      user: req.user._id
    });

    if (!job) {
      return res.status(404).json({
        success: false,
        message: 'Job not found'
      });
    }

    // Delete associated results
    await ScraperResult.deleteMany({ job: job._id });

    // Delete result file if exists
    if (job.resultFile) {
      try {
        await fs.unlink(job.resultFile);
      } catch (error) {
        logger.warn(`Could not delete result file: ${job.resultFile}`);
      }
    }

    await job.deleteOne();

    logger.info(`Job deleted: ${job._id}`);

    res.json({
      success: true,
      message: 'Job deleted successfully'
    });
  } catch (error) {
    next(error);
  }
};

/**
 * Start scraping process (background task)
 */
const startScraping = async (job) => {
  try {
    job.status = 'running';
    job.startedAt = Date.now();
    await job.save();

    // TODO: Integrate with your Python scrapers
    // For now, this is a placeholder
    logger.info(`Starting scraper for job ${job._id}`);

    // Simulate scraping process
    // In production, this would spawn Python process or use child_process
    // Example: const { spawn } = require('child_process');
    // const pythonProcess = spawn('python', ['scrapers/'+job.site+'.py', job.searchQuery]);

  } catch (error) {
    job.status = 'failed';
    job.error = {
      message: error.message,
      stack: error.stack
    };
    job.completedAt = Date.now();
    await job.save();
    logger.error(`Job failed: ${job._id}`, error);
  }
};

module.exports = {
  createJob,
  getJobs,
  getJobById,
  getJobResults,
  cancelJob,
  deleteJob
};