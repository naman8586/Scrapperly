const express = require('express');
const router = express.Router();
const {
  createJob,
  getJobs,
  getJobById,
  getJobResults,
  cancelJob,
  deleteJob
} = require('../controllers/scraperJobController');
const {
  getSites,
  getSiteFields,
  getScraperConfiguration
} = require('../controllers/scraperInfoController');
const { protect } = require('../middleware/auth');
const { scraperJobValidation } = require('../middleware/validation');

// Public routes - scraper info
router.get('/sites', getSites);
router.get('/sites/:site/fields', getSiteFields);
router.get('/config', getScraperConfiguration);

// Protected routes - job management
router.use(protect);

router.post('/jobs', scraperJobValidation, createJob);
router.get('/jobs', getJobs);
router.get('/jobs/:id', getJobById);
router.get('/jobs/:id/results', getJobResults);
router.put('/jobs/:id/cancel', cancelJob);
router.delete('/jobs/:id', deleteJob);

module.exports = router;