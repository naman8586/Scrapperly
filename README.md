# E-commerce Scraper Backend

Secure and scalable backend for managing e-commerce scraping jobs with user authentication.

## 🚀 Features

- **JWT Authentication** - Secure login/signup with access & refresh tokens
- **Account Security** - Rate limiting, failed login attempts tracking, account locking
- **Scraper Management** - Create, monitor, and manage scraping jobs
- **Real-time Progress** - Track scraping progress in real-time
- **Results Storage** - Store and retrieve scraped data efficiently
- **Concurrent Jobs** - Support for multiple simultaneous scraping operations
- **MongoDB Integration** - Scalable database with indexed queries
- **Error Handling** - Comprehensive error handling and logging

## 📋 Prerequisites

- Node.js >= 14.0.0
- MongoDB (local or Atlas)
- Python 3.x (for scrapers)

## 🛠️ Installation

### 1. Clone and Install Dependencies

```bash
npm install
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and update the values:

```bash
# Server
PORT=5000
NODE_ENV=development

# Frontend URLs (comma-separated)
FRONTEND_URLS=http://localhost:3000

# MongoDB
MONGODB_URI=mongodb://localhost:27017/ecommerce-scraper

# JWT (Generate secure random strings)
JWT_SECRET=your-super-secret-jwt-key-min-32-chars
JWT_EXPIRE=7d
JWT_REFRESH_SECRET=your-super-secret-refresh-token-key-min-32-chars
JWT_REFRESH_EXPIRE=30d

# Scraper Configuration
ALLOWED_SITES=alibaba,flipkart,amazon,dhgate,indiamart,madeinchina,ebay
MAX_CONCURRENT_SCRAPERS=3
SCRAPER_TIMEOUT=300000
```

### 3. Start MongoDB

**Local MongoDB:**
```bash
mongod
```

**Or use MongoDB Atlas** (cloud) and update `MONGODB_URI` in `.env`

### 4. Run the Server

**Development:**
```bash
npm run dev
```

**Production:**
```bash
npm start
```

Server will start on `http://localhost:5000`

## 📁 Project Structure

```
backend/
├── config/
│   └── database.js          # MongoDB connection
├── controllers/
│   ├── authController.js    # Authentication logic
│   └── scraperController.js # Scraper job management
├── middleware/
│   ├── auth.js              # JWT authentication
│   ├── errorHandler.js      # Error handling
│   └── validation.js        # Request validation
├── models/
│   ├── User.js              # User schema
│   ├── ScraperJob.js        # Scraper job schema
│   └── ScraperResult.js     # Scraped data schema
├── routes/
│   ├── authRoutes.js        # Auth endpoints
│   └── scraperRoutes.js     # Scraper endpoints
├── scrapers/                # Python scraper scripts
│   ├── scraper_template.py  # Template for integration
│   ├── alibaba.py
│   ├── amazon.py
│   └── ...
├── utils/
│   ├── jwt.js               # JWT utilities
│   ├── logger.js            # Winston logger
│   └── scraperExecutor.js   # Python scraper executor
├── app.js                   # Express app setup
├── server.js                # Server entry point
├── package.json
└── .env
```

## 🔌 API Endpoints

### Authentication

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/auth/register` | Register new user | No |
| POST | `/api/auth/login` | Login user | No |
| POST | `/api/auth/refresh` | Refresh access token | No |
| POST | `/api/auth/logout` | Logout user | Yes |
| GET | `/api/auth/me` | Get current user | Yes |

### Scraper Jobs

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/scraper/jobs` | Create scraping job | Yes |
| GET | `/api/scraper/jobs` | Get all user jobs | Yes |
| GET | `/api/scraper/jobs/:id` | Get job by ID | Yes |
| GET | `/api/scraper/jobs/:id/results` | Get job results | Yes |
| PUT | `/api/scraper/jobs/:id/cancel` | Cancel job | Yes |
| DELETE | `/api/scraper/jobs/:id` | Delete job | Yes |

## 📝 API Examples

### Register User

```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "email": "test@example.com",
    "password": "Test123!"
  }'
```

### Login

```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!"
  }'
```

### Create Scraper Job

```bash
curl -X POST http://localhost:5000/api/scraper/jobs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "site": "amazon",
    "searchQuery": "laptop",
    "selectedFields": ["title", "price", "rating"],
    "config": {
      "maxItems": 50
    }
  }'
```

## 🔧 Integrating Your Python Scrapers

### Step 1: Update Your Scraper

Use the provided template structure in `scrapers/scraper_template.py`:

```python
from scraper_template import ScraperTemplate

class AmazonScraper(ScraperTemplate):
    def scrape(self):
        # Your scraping logic
        items = self.scrape_amazon_products(self.query)
        total = min(len(items), self.max_items)
        
        self.send_progress(0, total)
        
        for index, item in enumerate(items[:self.max_items]):
            # Filter fields
            filtered_item = {
                field: item.get(field) 
                for field in self.fields 
                if field in item
            }
            
            self.send_item(filtered_item, item.get('url'), index)
            self.send_progress(index + 1, total)
```

### Step 2: Accept Command-line Arguments

Your scraper should accept:
- `--query`: Search query
- `--fields`: Comma-separated fields to scrape
- `--max-items`: Maximum items to scrape
- `--job-id`: Database job ID

### Step 3: Output Format

Send JSON to stdout:

**Progress Update:**
```json
{"type": "progress", "scraped": 10, "total": 50}
```

**Scraped Item:**
```json
{
  "type": "item",
  "item": {"title": "Product", "price": "$99"},
  "url": "https://...",
  "index": 0
}
```

## 🔒 Security Features

- **Password Hashing** - bcrypt with configurable rounds
- **JWT Tokens** - Separate access & refresh tokens
- **Rate Limiting** - Global and endpoint-specific limits
- **Account Locking** - After failed login attempts
- **CORS Protection** - Configurable allowed origins
- **Helmet.js** - Security headers
- **Input Validation** - express-validator
- **Request Sanitization** - Prevents injection attacks

## 📊 Database Schema

### Users Collection
```javascript
{
  username: String,
  email: String,
  password: String (hashed),
  role: "user" | "admin",
  isActive: Boolean,
  loginAttempts: Number,
  lockUntil: Date,
  refreshTokens: [{ token, createdAt }],
  lastLogin: Date
}
```

### ScraperJobs Collection
```javascript
{
  user: ObjectId,
  site: String,
  searchQuery: String,
  selectedFields: [String],
  status: "pending" | "running" | "completed" | "failed" | "cancelled",
  progress: Number,
  totalItems: Number,
  scrapedItems: Number,
  startedAt: Date,
  completedAt: Date,
  error: { message, stack },
  config: { maxItems, timeout, retryAttempts }
}
```

### ScraperResults Collection
```javascript
{
  job: ObjectId,
  user: ObjectId,
  site: String,
  data: Mixed,
  metadata: {
    scrapedAt: Date,
    url: String,
    itemIndex: Number
  }
}
```

## 🐛 Debugging

View logs in `./logs/`:
- `combined.log` - All logs
- `error.log` - Error logs only

Enable debug mode:
```bash
NODE_ENV=development npm run dev
```

## 📦 Production Deployment

### 1. Environment Setup

```bash
NODE_ENV=production
```

### 2. Use Process Manager

```bash
npm install -g pm2
pm2 start server.js --name ecommerce-scraper
```

### 3. MongoDB Atlas

Use MongoDB Atlas for production and update `MONGODB_URI`

### 4. Security Checklist

- [ ] Change all secret keys
- [ ] Use HTTPS
- [ ] Enable firewall
- [ ] Limit MongoDB access
- [ ] Set up monitoring
- [ ] Configure proper CORS
- [ ] Use environment-specific configs

## 🤝 Contributing

1. Ensure your Python scrapers follow the template
2. Test authentication flow
3. Verify scraper job creation and monitoring
4. Check error handling

## 📄 License

MIT

## 🆘 Support

For issues or questions, check logs and ensure:
- MongoDB is running
- Python is installed
- Environment variables are set
- Scraper files are in `scrapers/` directory