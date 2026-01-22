const { body, validationResult } = require('express-validator');

/**
 * Validate request and return errors if any
 */
const validate = (req, res, next) => {
  const errors = validationResult(req);
  if (!errors.isEmpty()) {
    return res.status(400).json({
      success: false,
      errors: errors.array().map(err => ({
        field: err.path,
        message: err.msg
      }))
    });
  }
  next();
};

/**
 * Registration validation rules
 */
const registerValidation = [
  body('username')
    .trim()
    .isLength({ min: 3, max: 30 })
    .withMessage('Username must be between 3 and 30 characters')
    .matches(/^[a-zA-Z0-9_]+$/)
    .withMessage('Username can only contain letters, numbers, and underscores'),
  
  body('email')
    .trim()
    .isEmail()
    .withMessage('Please provide a valid email')
    .normalizeEmail(),
  
  body('password')
    .isLength({ min: 6 })
    .withMessage('Password must be at least 6 characters')
    .matches(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)/)
    .withMessage('Password must contain at least one uppercase letter, one lowercase letter, and one number'),
  
  validate
];

/**
 * Login validation rules
 */
const loginValidation = [
  body('email')
    .trim()
    .isEmail()
    .withMessage('Please provide a valid email')
    .normalizeEmail(),
  
  body('password')
    .notEmpty()
    .withMessage('Password is required'),
  
  validate
];

/**
 * Scraper job validation rules
 */
const scraperJobValidation = [
  body('site')
    .trim()
    .notEmpty()
    .withMessage('Site is required')
    .isIn(process.env.ALLOWED_SITES?.split(',') || ['alibaba', 'flipkart', 'amazon', 'dhgate', 'indiamart', 'madeinchina', 'ebay'])
    .withMessage('Invalid site selection'),
  
  body('searchQuery')
    .trim()
    .notEmpty()
    .withMessage('Search query is required')
    .isLength({ min: 2, max: 200 })
    .withMessage('Search query must be between 2 and 200 characters'),
  
  body('selectedFields')
    .isArray({ min: 1 })
    .withMessage('At least one field must be selected'),
  
  body('selectedFields.*')
    .trim()
    .notEmpty()
    .withMessage('Field name cannot be empty'),
  
  body('config.maxItems')
    .optional()
    .isInt({ min: 1, max: 1000 })
    .withMessage('Max items must be between 1 and 1000'),
  
  validate
];

module.exports = {
  validate,
  registerValidation,
  loginValidation,
  scraperJobValidation
};