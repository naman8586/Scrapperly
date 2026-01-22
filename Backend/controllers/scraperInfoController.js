const {
  getAvailableSites,
  getAvailableFields,
  getDefaultFields,
  getScraperConfig
} = require('../config/scraperConfig');

/**
 * @desc    Get all available scraper sites
 * @route   GET /api/scraper/sites
 * @access  Public
 */
const getSites = async (req, res, next) => {
  try {
    const sites = getAvailableSites();
    
    res.json({
      success: true,
      data: sites
    });
  } catch (error) {
    next(error);
  }
};

/**
 * @desc    Get available fields for a specific site
 * @route   GET /api/scraper/sites/:site/fields
 * @access  Public
 */
const getSiteFields = async (req, res, next) => {
  try {
    const { site } = req.params;
    
    const config = getScraperConfig(site);
    const fields = getAvailableFields(site);
    const defaultFields = getDefaultFields(site);
    
    res.json({
      success: true,
      data: {
        site: config.name,
        fields,
        defaultFields
      }
    });
  } catch (error) {
    if (error.message.includes('Configuration not found')) {
      return res.status(404).json({
        success: false,
        message: error.message
      });
    }
    next(error);
  }
};

/**
 * @desc    Get configuration for all sites with their fields
 * @route   GET /api/scraper/config
 * @access  Public
 */
const getScraperConfiguration = async (req, res, next) => {
  try {
    const sites = getAvailableSites();
    const configuration = sites.map(site => ({
      id: site.id,
      name: site.name,
      fields: getAvailableFields(site.id),
      defaultFields: getDefaultFields(site.id)
    }));
    
    res.json({
      success: true,
      data: configuration
    });
  } catch (error) {
    next(error);
  }
};

module.exports = {
  getSites,
  getSiteFields,
  getScraperConfiguration
};