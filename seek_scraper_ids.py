import aiohttp
import asyncio
import json
import re
import time
import random
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel, HttpUrl
import uvicorn
import os
from datetime import datetime

# Import selenium package
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
import undetected_chromedriver as uc

# Create the API APP
app = FastAPI(
    title="Seek Job Cards Scraper API",
    description="A simple API to scrape job cards from Seek.com.au",
    version="1.0.0"
)

# Define the data model for the job search
class JobSearchRequest(BaseModel):
    search_url: HttpUrl
    posted_date_limit: Optional[str] = None

# Create class for all the functions regarding scraping
class SeekJobCardsScraper:
    
    def __init__(self, use_selenium=True):
        """
        Initialize the scraper with base URL and headers for requests

        Args:
            use_selenium: Boolean to determine to use selenium and not aiohttp
        """
        self.base_url = "https://www.seek.com.au"  # Define the main URL that will be used
        self.use_selenium = use_selenium
        self.timeout = 30  # Timeout in seconds for HTTP requests
        
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Safari/605.1.15'
        ]  # set the rotation of browsers
        
        if use_selenium:
            self._setup_selenium()
        else:
            # Keep the aiohttp setup as backup
            self.headers = {
                'User-Agent': random.choice(self.user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1'
            }

    def _setup_selenium(self):
        """
        Set up the Selenium web driver with Chrome
        """
        # Set up the Chrome options
        chrome_options = Options()
        
        chrome_options.add_argument('--ignore-certificate-errors')
        chrome_options.add_argument('--allow-insecure-localhost')
        chrome_options.add_argument('--ignore-ssl-errors=yes')
        chrome_options.add_argument('--disable-web-security')

        # Add headless option for server environments
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")

        # Add additional privacy options to avoid detection
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)

        # Set user agent - Picks randomly from the list
        chrome_options.add_argument(f"user-agent={random.choice(self.user_agents)}")
    
        chromedriver_path = '/usr/local/bin/chromedriver'
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),  # change to chromedriver_path to use in sevalla
            options=chrome_options
        )
            
        # Set window size
        self.driver.set_window_size(1200, 720)
        
        # Execute JavaScript to mask WebDriver presence
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")    

    async def __aenter__(self):
        """Set up resources when entering context"""
        if not self.use_selenium:
            # Only set up aiohttp if not using Selenium
            self.session = aiohttp.ClientSession(headers=self.headers)
            
            # Make an initial request to get cookies
            try:
                async with self.session.get(self.base_url) as response:
                    if response.status == 200:
                        print("Successfully initialized session with cookies")
            except Exception as e:
                print(f"Error initializing session: {str(e)}")
                
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context"""
        if self.use_selenium:
            self.driver.quit()
        else:
            await self.session.close()

    def extract_job_id(self, url: str) -> str:
        """
        Extract job ID from URL.
        
        Args:
            url: The job posting URL
            
        Returns:
            The job ID extracted from the URL
        """
        try:
            # Find the part after 'job/' and before '?'
            start_index = url.find('/job/') + 5  # +5 to skip '/job/'
            end_index = url.find('?', start_index)
            
            if end_index == -1:  # If there's no '?', take until the end
                return url[start_index:]
            return url[start_index:end_index]
        
        except Exception as e:
            return "Job ID not found"

    async def fetch_page(self, url: str, max_retries: int = 3) -> BeautifulSoup:
        """
        Fetch a webpage and return a BeautifulSoup object using either Selenium or aiohttp
        """
        if self.use_selenium:
            return await self._fetch_with_selenium(url, max_retries)
        else:
            return await self._fetch_with_aiohttp(url, max_retries)

    async def _fetch_with_selenium(self, url: str, max_retries: int = 3) -> BeautifulSoup:
        """
        Fetch a webpage using Selenium
        """
        for attempt in range(max_retries):
            try:
                # Execute in an asyncio executor to avoid blocking
                loop = asyncio.get_event_loop()
                
                # Load the page
                await loop.run_in_executor(None, lambda: self.driver.get(url))
                
                # Add a random delay to simulate human behavior
                await asyncio.sleep(random.uniform(2, 5))
                
                # Wait for the page content to load 
                await loop.run_in_executor(
                    None, 
                    lambda: WebDriverWait(self.driver, self.timeout).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                )
                
                # Get page source
                html = await loop.run_in_executor(None, lambda: self.driver.page_source)
                
                # Parse with BeautifulSoup
                return BeautifulSoup(html, 'html.parser')
                
            except TimeoutException:
                print(f"Timeout on attempt {attempt + 1} for {url}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                
            except WebDriverException as e:
                print(f"WebDriver error on attempt {attempt + 1} for {url}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    
                    # Refresh the WebDriver if we encounter issues
                    if "ERR_INTERNET_DISCONNECTED" in str(e) or "invalid session id" in str(e):
                        self.driver.quit()
                        self._setup_selenium()
                        
            except Exception as e:
                print(f"Unexpected error on attempt {attempt + 1} for {url}: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        print(f"Failed to fetch {url} after {max_retries} attempts")
        return None    

    async def _fetch_with_aiohttp(self, url: str, max_retries: int = 3) -> BeautifulSoup:
        """
        Fetch a webpage using aiohttp (kept as a fallback)
        """
        for attempt in range(max_retries):
            try:
                # Update headers with random user agent
                self.session.headers.update({'User-Agent': random.choice(self.user_agents)})
                
                async with self.session.get(url, timeout=self.timeout) as response:
                    if response.status == 200:
                        html = await response.text()
                        return BeautifulSoup(html, 'html.parser')
                    elif response.status == 403:
                        print(f"Received 403 Forbidden. Waiting before retry.")
                        wait_time = 2 ** attempt  # Exponential backoff
                        await asyncio.sleep(wait_time)
                    else:
                        print(f"Error fetching {url}: HTTP {response.status}")
            except Exception as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    print(f"Failed after {max_retries} attempts")
                    raise
        return None

        #This function will get the next page URL
    def get_next_page_url(self, soup: BeautifulSoup, current_page: int) -> str:
        """
        Get the URL for the next page of search results
        
        Args:
            soup: BeautifulSoup object of the current page
            current_page: Current page number
            
        Returns:
            URL of the next page, or None if there is no next page
        """
        try:
            next_page_num = current_page + 1
            
            # Look for the next page link
            next_page_element = soup.select_one(f'[data-automation="page-{next_page_num}"]')
            
            if next_page_element and next_page_element.has_attr('href'):
                href = next_page_element['href']
                return urljoin(self.base_url, href)
                
            return None
            
        except Exception as e:
            print(f"Error getting next page URL: {str(e)}")
            return None
    
    
    
    def sanitize_text(self, text):
        """
        Helps sanitize the text extracted from the website, avoiding Unicode errors.
        """
        if not isinstance(text, str):
            return str(text)
    
        # Replace surrogate pairs and other problematic characters
        try:
            # First attempt: encode with surrogateescape and decode back
            return text.encode('utf-8', 'surrogateescape').decode('utf-8', 'replace')
        except UnicodeError:
            # Second attempt: more aggressive replacement
            return text.encode('utf-8', 'replace').decode('utf-8')

    def _convert_to_days(self, posted_time: str) -> float:
        """
        Convert posting time string to number of days
        
        Args:
            posting_time: String representing when the job was posted (e.g., "Posted 2d ago")
            
        Returns:
            Float representing the number of days
        """
        print(f"\nConverting posting time: {posted_time}")
        
        try:
            if not posted_time or 'not found' in posted_time:
                print("Invalid posting time, returning infinity")
                return float('inf')
            
            # Remove "Posted" prefix and clean the string
            cleaned_posted_time = posted_time.lower().replace('posted', '').strip()
            print(f"Cleaned time string: {cleaned_posted_time}")

            # Match a number followed by m (minutes), h (hours), or d (days)
            match = re.match(r'(\d+)\s*([mhd])', cleaned_posted_time)
            if not match:
                print(f"Could not parse time format: {cleaned_posted_time}")
                return float('inf')
                        
            value, unit = match.groups()
            value = float(value)
                    
            # Convert to days based on unit
            if unit == 'm':
                days = value / (24 * 60)
                print(f"Converting {value} minutes to {days:.2f} days")
            elif unit == 'h':
                days = value / 24
                print(f"Converting {value} hours to {days:.2f} days")
            else:  # unit == 'd'
                days = value
                print(f"Already in days: {days}")
                        
            return days
                    
        except Exception as e:
            print(f"Error converting time: {str(e)}")
            return float('inf')
    
    def _is_within_time_limit(self, posted_date: str, posted_date_limit: str) -> bool:
        """
        Check if a posting time is within the specified time limit
        
        Args:
            posting_time: String representing when the job was posted
            time_limit: String representing the maximum age of posts to include
            
        Returns:
            Boolean indicating if the job posting is within the time limit
        """
        if not posted_date_limit:
            return True
            
        job_days = self._convert_to_days(posted_date)
        limit_days = self._convert_to_days(posted_date_limit)
        
        print(f"Comparing job time ({job_days:.2f} days) with limit ({limit_days:.2f} days)")
        return job_days < limit_days

    def extract_posting_time(self, job_card) -> str:
        """
        Extract posting time from a job card element
        
        Args:
            job_card: BeautifulSoup element representing a job card
            
        Returns:
            String representing when the job was posted
        """
        try:
            # Look for the time element in the job card
            time_element = job_card.select_one('[data-automation="jobListingDate"], .TWZc6b0, span:contains("Posted")')
            
            if time_element:
                return self.sanitize_text(time_element.text.strip())
            
            # Alternative approach: look for spans with 'Posted' text
            for span in job_card.select('span'):
                text = span.text.strip()
                if 'Posted' in text and any(unit in text for unit in ['ago', 'h', 'd', 'm']):
                    return self.sanitize_text(text)
            
            return "Posting time not found"
            
        except Exception as e:
            print(f"Error extracting posting time: {str(e)}")
            return "Posting time not found"

    async def scrape_job_cards(self, search_url: str, posted_date_limit: str = None) -> List[Dict]:
        """
        Scrape job cards from the current search page to extract job_id and posted_date
        
        Args:
            search_url: Search URL to scrape
            posted_date_limit: Only include jobs posted within this time frame (e.g., "1d ago")
            
        Returns:
            List of dictionaries containing job_id and posted_date
        """
        try:
            print(f"Starting job cards scrape with search URL: {search_url}")
            
            job_cards_data = []
            current_page = 1
            job_scraped = 0
            current_url = search_url
            
            while True:
                print(f"Scraping page {current_page}")

                # Fetch the current page with retries
                soup = await self.fetch_page(current_url, max_retries=3)
                if not soup:
                    print("Failed to get BS object")
                    return []
                
                # Find all job cards
                job_cards = soup.select('article[data-automation="normalJob"], [data-automation="jobCard"]')
                print(f"Found {len(job_cards)} job cards on the page")

                # Process each job card
                for card in job_cards:
                    
                    try:
                        # Get the job link
                        link_element = card.select_one('a')
                        if not link_element or not link_element.has_attr('href'):
                            continue

                        href = link_element['href']
                        job_url = urljoin(self.base_url, href)
                        job_id = self.extract_job_id(job_url)
                        print(f"\n Processing job: {job_scraped +1}")
                        
                        # Extract posting time directly from the job card
                        posted_date = self.extract_posting_time(card)
                                                                      
                        # Check if job is within time limit
                        if posted_date_limit and not self._is_within_time_limit(posted_date, posted_date_limit):
                                print(f"Job outside time limit, skipping")
                                return job_cards_data   
                            
                            # Add to results
                        job_cards_data.append({
                                'job_id': job_id,
                                'posted_date': posted_date,
                                'url': job_url}) 
                            
                        job_scraped += 1
                        print(f"Successfully scraped")
                            
                    except Exception as e:
                        print(f"Error processing job card: {str(e)}")
                        continue


                # Add a random delay between pages
                await asyncio.sleep(random.uniform(3, 7))        
            
                next_page_url = self.get_next_page_url(soup, current_page)
                if not next_page_url:
                    print("No next page found, ending scrape")
                    break
            
                current_url = next_page_url
                current_page += 1
                await asyncio.sleep(1)  # Small delay between pages to avoid rate limiting

            return job_cards_data

        except Exception as e:
            print(f"Error in scrape_job_cards: {str(e)}")
            return []


async def save_to_json(self, jobs_data: List[Dict], filename: str = 'seek_job_cards.json'):
        """
        Save scraped job data to a JSON file
        
        Args:
            jobs_data: List of job data dictionaries
            filename: Name of the output JSON file
        """
        # Ensure all job details are fully resolved
        scraped_jobs = []
        for job in jobs_data:
            # Create a new dict with resolved values
            scraped_job = {}
            for key, value in job.items():
                if key == 'posted_date':
                    # Ensure these values are strings
                    scraped_job[key] = self.sanitize_text(value)
                else:
                    scraped_job[key] = value
            scraped_jobs.append(scraped_job)

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(scraped_jobs, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {len(scraped_jobs)} job cards to {filename}")


# Creates a directory to save the results if it doesnt exists
RESULTS_DIR = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)


# Define the API endpoints

@app.get("/")
async def root():
    """Root endpoint that returns basic API information"""
    return {
        "message": "Welcome to the Seek Job Cards Scraper API",
        "version": "1.0.0",
        "endpoints": {
            "/scrape": "POST - Scrape job cards based on search criteria and return results",
            "/health": "GET - Check API health status"
        }
    }

@app.get("/health_ids")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# Scrape endpoint
@app.post("/scrape_ids")
async def scrape_job_cards_endpoint(request: JobSearchRequest):
    """
    Endpoint to scrape job cards based on search criteria
    
    Returns the scraped job cards data directly in the response
    """
    try:
        start_time = time.time()    

        # Run the scraper
        async with SeekJobCardsScraper(use_selenium=True) as scraper:
            jobs_data = await scraper.scrape_job_cards(
                str(request.search_url),
                posted_date_limit=request.posted_date_limit
            )

        elapsed_time = time.time() - start_time
        
        # Ensure all values are properly serializable
        serializable_jobs = []
        for job in jobs_data:
            serializable_job = {}
            for key, value in job.items():
                # Use sanitize_text for string values
                if isinstance(value, str):
                    serializable_job[key] = scraper.sanitize_text(value)
                elif isinstance(value, (type, object)) and not isinstance(value, (int, float, bool, str, list, dict, type(None))):
                    serializable_job[key] = str(value)
                else:
                    serializable_job[key] = value

            serializable_jobs.append(serializable_job)
        
        return {
            "status": "success",
            "job_card_count": len(serializable_jobs),
            "execution_time": round(elapsed_time, 2),
            "data": serializable_jobs
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Scraping failed: {str(e)}"
        )


if __name__ == "__main__":
    # Determine port - use environment variable if available
    port = int(os.environ.get("PORT", 8080))
    
    # Run the API server
    uvicorn.run("seek_job_cards_scraper:app", host="0.0.0.0", port=port, reload=False)

# Run server manually
## uvicorn seek_job_cards_scraper:app --reload