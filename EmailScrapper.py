import requests
from bs4 import BeautifulSoup
import re
import csv
import time
import random
from fake_useragent import UserAgent
import urllib.parse
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# List of user agents to rotate (if fake_useragent fails)
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0'
]


# Function to get a random user agent
def get_random_user_agent():
    try:
        ua = UserAgent()
        return ua.random
    except:
        return random.choice(USER_AGENTS)


# Function to initialize selenium webdriver
def init_driver(headless=True):
    options = Options()
    if headless:
        options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--user-agent={get_random_user_agent()}')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('useAutomationExtension', False)
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver


# Function to check if robots.txt allows scraping
def can_scrape(url):
    try:
        parsed_url = urllib.parse.urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        response = requests.get(robots_url, timeout=5)
        return "Disallow: /" not in response.text
    except:
        return True  # If can't check robots.txt, assume scraping is allowed


# Function to find contact page URLs
def find_contact_pages(soup, base_url):
    contact_links = set()
    contact_keywords = ['contact', 'kontakt', 'contacto', 'about', 'connect', 'get in touch', 'email us']

    for link in soup.find_all('a', href=True):
        href = link.get('href')
        text = link.text.lower().strip()

        if not href or href.startswith(('javascript:', '#', 'tel:')):
            continue

        # Check if link text or href suggests it's a contact page
        if any(keyword in text for keyword in contact_keywords) or any(
                keyword in href.lower() for keyword in contact_keywords):
            full_url = urllib.parse.urljoin(base_url, href)
            contact_links.add(full_url)

    return contact_links


# Function to scrape emails using requests
def scrape_emails_with_requests(url):
    emails = set()
    try:
        headers = {
            'User-Agent': get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://www.google.com/',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Cache-Control': 'max-age=0',
        }

        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            emails.update(extract_emails_from_soup(soup))

            # Check for contact pages
            contact_pages = find_contact_pages(soup, url)
            for contact_url in contact_pages:
                logger.info(f"Checking contact page: {contact_url}")
                time.sleep(random.uniform(3, 7))  # Random delay between requests

                try:
                    contact_response = session.get(contact_url, headers={'User-Agent': get_random_user_agent()},
                                                   timeout=15)
                    if contact_response.status_code == 200:
                        contact_soup = BeautifulSoup(contact_response.text, 'html.parser')
                        emails.update(extract_emails_from_soup(contact_soup))
                except Exception as e:
                    logger.error(f"Error on contact page {contact_url}: {e}")

        return emails
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error for {url}: {e}")
        return emails


# Function to scrape emails using Selenium (for CAPTCHA cases)
def scrape_emails_with_selenium(url):
    emails = set()
    driver = None
    try:
        logger.info(f"Using Selenium for: {url}")
        driver = init_driver()
        driver.get(url)
        # Wait for page to load - helps with dynamic content
        time.sleep(5)

        # Extract emails from main page
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        emails.update(extract_emails_from_soup(soup))

        # Find and visit contact pages
        contact_links = find_contact_pages(soup, url)
        for contact_url in contact_links:
            logger.info(f"Selenium checking contact page: {contact_url}")
            try:
                # Random delay between page navigations
                time.sleep(random.uniform(4, 8))
                driver.get(contact_url)
                time.sleep(5)  # Wait for page to load

                contact_soup = BeautifulSoup(driver.page_source, 'html.parser')
                emails.update(extract_emails_from_soup(contact_soup))
            except Exception as e:
                logger.error(f"Selenium error on contact page {contact_url}: {e}")

        return emails
    except Exception as e:
        logger.error(f"Selenium error for {url}: {e}")
        return emails
    finally:
        if driver:
            driver.quit()


# Function to extract emails from soup object
def extract_emails_from_soup(soup):
    emails = set()

    # Extract from text
    text = soup.get_text()
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails.update(re.findall(email_pattern, text))

    # Extract from mailto links
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if href.startswith('mailto:'):
            email = href[7:].split('?')[0]  # Remove mailto: prefix and parameters
            if re.match(email_pattern, email):
                emails.add(email)

    # Check for obfuscated emails (common technique)
    for script in soup.find_all('script'):
        script_text = script.string
        if script_text:
            # Look for common email obfuscation patterns
            potential_emails = re.findall(
                r'[\'"]([a-zA-Z0-9._%+-]+)[\'"][\s]*\+[\s]*[\'"]\@[\s]*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})[\'"]',
                script_text)
            for parts in potential_emails:
                if len(parts) == 2:
                    emails.add(f"{parts[0]}@{parts[1]}")

    return emails


# Main scraping function that tries requests first, falls back to Selenium
def scrape_emails(url):
    if not can_scrape(url):
        logger.info(f"Skipping {url} due to robots.txt restrictions")
        return set()

    # Try with regular requests first
    emails = scrape_emails_with_requests(url)

    # If no emails found or if URL likely has CAPTCHA protection
    if not emails or any(domain in url for domain in ['cloudflare', 'google', 'facebook']):
        emails.update(scrape_emails_with_selenium(url))

    return emails


def main():
    input_csv = "assets/email_scrap.csv"
    output_csv = "emails_output.csv"

    # Read websites from CSV
    websites = []
    with open(input_csv, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        websites = [row["website"] for row in reader if row["website"].startswith("http")]

    results = []
    for i, url in enumerate(websites):
        logger.info(f"[{i + 1}/{len(websites)}] Scraping {url}...")

        # Add randomized delays between websites
        if i > 0:
            delay = random.uniform(8, 15)
            logger.info(f"Waiting {delay:.1f} seconds before next website...")
            time.sleep(delay)

        emails = scrape_emails(url)
        results.append({
            "website": url,
            "emails": ", ".join(emails) if emails else "No emails found"
        })

        # Periodically save results in case of crashes
        if (i + 1) % 5 == 0:
            with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
                fieldnames = ["website", "emails"]
                writer = csv.DictWriter(file, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(results)
                logger.info(f"Progress saved after {i + 1} websites")

    # Write final results
    with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ["website", "emails"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    logger.info(f"Scraping complete. Results saved to {output_csv}")


if __name__ == "__main__":
    main()