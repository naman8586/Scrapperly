/**
 * Configuration for available scraper sites and their supported fields
 */

const scraperConfig = {
  madeinchina: {
    name: 'Made in China',
    fields: [
      { id: 'title', label: 'Product Title', type: 'string' },
      { id: 'exact_price', label: 'Price', type: 'string' },
      { id: 'currency', label: 'Currency', type: 'string' },
      { id: 'min_order', label: 'Minimum Order Quantity', type: 'string' },
      { id: 'supplier', label: 'Supplier Name', type: 'string' },
      { id: 'origin', label: 'Product Origin', type: 'string' },
      { id: 'feedback', label: 'Supplier Feedback/Rating', type: 'object' },
      { id: 'specifications', label: 'Product Specifications', type: 'object' },
      { id: 'images', label: 'Product Images', type: 'array' },
      { id: 'videos', label: 'Product Videos', type: 'array' },
      { id: 'brand_name', label: 'Brand Name', type: 'string' },
      { id: 'discount_information', label: 'Discount Info', type: 'string' }
    ],
    defaultFields: ['title', 'exact_price', 'supplier']
  },
  
  alibaba: {
    name: 'Alibaba',
    fields: [
      { id: 'title', label: 'Product Title', type: 'string' },
      { id: 'price', label: 'Price Range', type: 'string' },
      { id: 'moq', label: 'Minimum Order Quantity', type: 'string' },
      { id: 'supplier', label: 'Supplier Name', type: 'string' },
      { id: 'location', label: 'Supplier Location', type: 'string' },
      { id: 'images', label: 'Product Images', type: 'array' },
      { id: 'rating', label: 'Supplier Rating', type: 'string' },
      { id: 'years_in_business', label: 'Years in Business', type: 'string' }
    ],
    defaultFields: ['title', 'price', 'supplier']
  },
  
  amazon: {
    name: 'Amazon',
    fields: [
      { id: 'title', label: 'Product Title', type: 'string' },
      { id: 'price', label: 'Price', type: 'string' },
      { id: 'rating', label: 'Star Rating', type: 'string' },
      { id: 'reviews', label: 'Number of Reviews', type: 'string' },
      { id: 'availability', label: 'Stock Status', type: 'string' },
      { id: 'images', label: 'Product Images', type: 'array' },
      { id: 'description', label: 'Product Description', type: 'string' },
      { id: 'features', label: 'Product Features', type: 'array' },
      { id: 'asin', label: 'ASIN', type: 'string' }
    ],
    defaultFields: ['title', 'price', 'rating']
  },
  
  flipkart: {
    name: 'Flipkart',
    fields: [
      { id: 'title', label: 'Product Title', type: 'string' },
      { id: 'price', label: 'Price', type: 'string' },
      { id: 'rating', label: 'Star Rating', type: 'string' },
      { id: 'reviews', label: 'Number of Reviews', type: 'string' },
      { id: 'images', label: 'Product Images', type: 'array' },
      { id: 'seller', label: 'Seller Name', type: 'string' },
      { id: 'delivery', label: 'Delivery Info', type: 'string' }
    ],
    defaultFields: ['title', 'price', 'rating']
  },
  
  dhgate: {
    name: 'DHgate',
    fields: [
      { id: 'title', label: 'Product Title', type: 'string' },
      { id: 'price', label: 'Price', type: 'string' },
      { id: 'moq', label: 'Minimum Order', type: 'string' },
      { id: 'supplier', label: 'Supplier Name', type: 'string' },
      { id: 'images', label: 'Product Images', type: 'array' },
      { id: 'shipping', label: 'Shipping Info', type: 'string' }
    ],
    defaultFields: ['title', 'price', 'supplier']
  },
  
  indiamart: {
    name: 'IndiaMART',
    fields: [
      { id: 'title', label: 'Product Title', type: 'string' },
      { id: 'price', label: 'Price', type: 'string' },
      { id: 'supplier', label: 'Supplier Name', type: 'string' },
      { id: 'location', label: 'Supplier Location', type: 'string' },
      { id: 'images', label: 'Product Images', type: 'array' },
      { id: 'contact', label: 'Contact Info', type: 'string' }
    ],
    defaultFields: ['title', 'price', 'supplier']
  },
  
  ebay: {
    name: 'eBay',
    fields: [
      { id: 'title', label: 'Product Title', type: 'string' },
      { id: 'exact_price', label: 'Price', type: 'string' },
      { id: 'currency', label: 'Currency', type: 'string' },
      { id: 'description', label: 'Product Description', type: 'string' },
      { id: 'supplier', label: 'Seller Name', type: 'string' },
      { id: 'feedback', label: 'Seller Feedback (Rating & Reviews)', type: 'object' },
      { id: 'origin', label: 'Item Location', type: 'string' },
      { id: 'image_url', label: 'Primary Image', type: 'string' },
      { id: 'images', label: 'All Product Images', type: 'array' },
      { id: 'dimensions', label: 'Product Dimensions/Specifications', type: 'string' },
      { id: 'discount_information', label: 'Discount Info', type: 'string' },
      { id: 'brand_name', label: 'Brand Name', type: 'string' },
      { id: 'min_order', label: 'Minimum Order', type: 'string' }
    ],
    defaultFields: ['title', 'exact_price', 'supplier']
  }
};

/**
 * Get configuration for a specific site
 */
const getScraperConfig = (site) => {
  const config = scraperConfig[site.toLowerCase()];
  if (!config) {
    throw new Error(`Configuration not found for site: ${site}`);
  }
  return config;
};

/**
 * Get available fields for a site
 */
const getAvailableFields = (site) => {
  const config = getScraperConfig(site);
  return config.fields;
};

/**
 * Get default fields for a site
 */
const getDefaultFields = (site) => {
  const config = getScraperConfig(site);
  return config.defaultFields;
};

/**
 * Validate fields for a site
 */
const validateFields = (site, fields) => {
  const config = getScraperConfig(site);
  const validFieldIds = config.fields.map(f => f.id);
  const invalidFields = fields.filter(f => !validFieldIds.includes(f));
  
  return {
    isValid: invalidFields.length === 0,
    invalidFields,
    validFields: fields.filter(f => validFieldIds.includes(f))
  };
};

/**
 * Get all available sites
 */
const getAvailableSites = () => {
  return Object.keys(scraperConfig).map(key => ({
    id: key,
    name: scraperConfig[key].name
  }));
};

module.exports = {
  scraperConfig,
  getScraperConfig,
  getAvailableFields,
  getDefaultFields,
  validateFields,
  getAvailableSites
};