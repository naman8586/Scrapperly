require('dotenv').config();
const express = require('express');
const cors = require('cors');
const winston = require('winston');
const path = require('path');
const scraperRouter = require('./routes/ScraperRoutes');

const app = express();

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
      filename: path.join(__dirname, 'logs', 'server.log'),
      maxsize: 10 * 1024 * 1024, // 10MB
      maxFiles: 3,
    }),
  ],
});

// Log server startup
logger.info({ message: '🚀 Starting server...' });

// Validate environment variables
const PORT = process.env.PORT || 5000;
const FRONTEND_URLS = process.env.FRONTEND_URLS
  ? process.env.FRONTEND_URLS.split(',').map((s) => s.trim())
  : ['http://localhost:3000']; // Match frontend port
const ALLOWED_SITES = process.env.ALLOWED_SITES
  ? process.env.ALLOWED_SITES.split(',').map((s) => s.trim().toLowerCase())
  : [];

if (!process.env.FRONTEND_URLS) {
  logger.warn({ message: '⚠️ FRONTEND_URLS not set in .env. Defaulting to http://localhost:3000' });
}
if (ALLOWED_SITES.length === 0) {
  logger.error({ message: '❌ ALLOWED_SITES must be defined in .env' });
  process.exit(1);
}

// Middleware
app.use(
  cors({
    origin: (origin, callback) => {
      if (!origin || FRONTEND_URLS.includes(origin)) {
        callback(null, true);
      } else {
        callback(new Error('Not allowed by CORS'));
      }
    },
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Content-Type'],
    credentials: false,
  })
);
app.use(express.json());

// Request logging middleware
app.use((req, res, next) => {
  logger.info({
    message: 'Incoming request',
    method: req.method,
    url: req.originalUrl,
    body: req.method === 'POST' ? req.body : undefined,
    origin: req.get('origin'),
  });
  next();
});

// Routes
app.get('/', (req, res) => {
  res.json({ message: '🛍️ Ecom Scraper API' });
});

app.get('/health', (req, res) => {
  res.status(200).json({ status: 'healthy', uptime: process.uptime() });
});

app.use('/api', scraperRouter);

// Global error handler
app.use((err, req, res, next) => {
  logger.error({
    message: 'Unhandled server error',
    error: err.message,
    stack: err.stack,
    method: req.method,
    url: req.originalUrl,
    body: req.body,
  });
  res.status(500).json({
    message: 'Internal server error',
    error: process.env.NODE_ENV === 'development' ? err.message : undefined,
  });
});

// Start server
app.listen(PORT, () => {
  logger.info({ message: `✅ Server running at http://localhost:${PORT}` });
});