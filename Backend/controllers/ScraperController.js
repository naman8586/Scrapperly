const ScraperJob = require('../models/ScraperJob');
const ScraperResult = require('../models/ScraperResult');
const logger = require('../utils/logger');
const path = require('path');
const fs = require('fs').promises;

const getScraperModule = (site) => {
  try {
    return require(`../scrapers/${site}.py`);
  } catch (error) {
    logger.warn(`Scraper module not found for ${site}`);
    return null;
  }
};

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

const startScraping = async (job) => {
  try {
    job.status = 'running';
    job.startedAt = Date.now();
    await job.save();

    logger.info(`Starting scraper for job ${job._id}`);

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
