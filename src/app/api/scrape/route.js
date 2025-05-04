import { NextResponse } from 'next/server';
import { spawn } from 'child_process';
import { kv } from '@vercel/kv';

export async function POST(request) {
  try {
    const { website, keyword, attributes } = await request.json();

    // Validate inputs
    const validSites = [
      'Alibaba',
      'eBay',
      'DHgate',
      'Amazon',
      'Flipkart',
      'MadeInChina',
      'IndiaMart',
    ];
    if (!validSites.includes(website)) {
      return NextResponse.json({ error: 'Invalid website' }, { status: 400 });
    }
    if (!keyword || !attributes.length) {
      return NextResponse.json({ error: 'Missing parameters' }, { status: 400 });
    }

    // Check cache
    const cacheKey = `${website}:${keyword}:${attributes.join(',')}`;
    const cached = await kv.get(cacheKey);
    if (cached) {
      return NextResponse.json(cached);
    }

    // Map website to scraper script
    const scraperMap = {
      Alibaba: 'alibaba_scraper.py',
      eBay: 'ebay_scraper.py',
      DHgate: 'dhgate_scraper.py',
      Amazon: 'amazon_scraper.py',
      Flipkart: 'flipkart_scraper.py',
      MadeInChina: 'madeinchina_scraper.py',
      IndiaMart: 'indiamart_scraper.py',
    };

    const script = scraperMap[website];
    if (!script) {
      return NextResponse.json({ error: 'Scraper not found' }, { status: 400 });
    }

    // Run Python scraper
    const python = spawn('python3', [
      `./scrapers/${script}`,
      website,
      keyword,
      JSON.stringify(attributes),
    ]);

    let output = '';
    let errorOutput = '';

    python.stdout.on('data', (data) => {
      output += data.toString();
    });

    python.stderr.on('data', (data) => {
      errorOutput += data.toString();
    });

    const results = await new Promise((resolve, reject) => {
      python.on('close', (code) => {
        if (code !== 0) {
          reject(new Error(`Scraping failed: ${errorOutput}`));
        }
        try {
          resolve(JSON.parse(output));
        } catch (error) {
          reject(new Error('Invalid scraper output'));
        }
      });
    });

    // Cache results
    await kv.set(cacheKey, results, { ex: 3600 }); // Cache for 1 hour

    return NextResponse.json(results);
  } catch (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}