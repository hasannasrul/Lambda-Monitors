from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from tempfile import mkdtemp
from urllib.parse import urlparse
import requests
import boto3
import os
import json
from datetime import datetime
from io import BytesIO
from PIL import Image
import time
import random


s3 = boto3.client('s3')

######################     Some utility functions    ############################################
user_agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/14.0.3',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:95.0) Gecko/20100101 Firefox/95.0',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 15_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 10; SM-A505U) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.45 Mobile Safari/537.36'
]

def upload_logs_to_s3(logs, bucket_name, key):
    logs_str = json.dumps(logs, indent=2)
    s3.put_object(Body=logs_str, Bucket=bucket_name, Key=key)

def extract_domain_from_url(url):
        parsed_url = urlparse(url)
        return parsed_url.netloc

# External URLs are those url which are not in sitemap.xml
def get_external_url(urls,website_domain):
    external_urls = []
    for url in urls:
        parsed_url = urlparse(url)
        # Check if the netloc (domain) of the parsed URL is different from the website's domain
        if parsed_url.netloc and parsed_url.netloc != website_domain:
            external_urls.append(url)
    return external_urls

############### Monitor class to implement monitoring features ##############################

class Monitor():
    def __init__(self, driver):
        self.driver = driver

    def get_page_availability(self, url):
        try:
            self.driver.get(url)
            # Take a screenshot
            screenshot = self.driver.get_screenshot_as_png()
            screenshot_image = Image.open(BytesIO(screenshot))
            # Create a timestamp for the screenshot key
            timestamp = int(time.time() * 1000)

            screenshot_key = f'evidence/{extract_domain_from_url(url)}_{timestamp}_evidence.png'

            # Save the screenshot locally
            screenshot_path = f'/tmp/{extract_domain_from_url(url)}_evidence.png'
            screenshot_image.save(screenshot_path)

            # Upload the screenshot to S3
            s3.upload_file(screenshot_path, os.environ['S3_BUCKET_NAME'], screenshot_key)

            return True, screenshot_key
        
        except Exception as e:
            # Capture a screenshot even if the URL is not reachable
            screenshot_key = f'evidence/{extract_domain_from_url(url)}_error_evidence.png'
            screenshot_path = f'/tmp/{extract_domain_from_url(url)}_{timestamp}_error_evidence.png'
            self.driver.save_screenshot(screenshot_path)
            # Upload the screenshot to S3
            s3.upload_file(screenshot_path, os.environ['S3_BUCKET_NAME'], screenshot_key)
            return False, screenshot_key

    def get_page_load_time(self):
        navigation_start = self.driver.execute_script("return window.performance.timing.navigationStart;")
        load_event_end = self.driver.execute_script("return window.performance.timing.loadEventEnd;")
        page_load_time = (load_event_end - navigation_start) / 1000.0  # Convert to seconds
        return page_load_time

    def check_console_errors(self):
        console_errors = self.driver.get_log("browser")
        return console_errors

    def ping_external_url(self,urls):
        results = []
        session = requests.Session()
        
        for url in urls:
            try:
                # Create headers mimicking Google Chrome
                headers = {
                    'User-Agent': random.choice(user_agents),
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Referer': 'https://www.google.com/',
                }

                # Use the session to make the request
                response = session.get(url, headers=headers)
                
                # If the response code is 2xx, the site is accessible
                if 200 <= response.status_code < 300:
                    pass # Append nothing in the result array because site is okay
                    # results.append({url: None})
                else:
                    results.append({url: f"Unexpected response code: {response.status_code}"})
            
            except requests.RequestException as e:
                # Handle request exceptions
                results.append({url: f"RequestException: {str(e)}"})
        
        return results        

############### Actual Lambda Handler function ##############################

def handler(event, context):
    # Extract URL,Exception List from the event
    url = event.get('url')

    # Check if the URL is provided
    if not url:
        return {
            'statusCode': 400,
            'body': 'Error: Missing URL in the event'
        }

    driver = None  # Initialize the driver variable
    
    try:
        # Set up Chrome WebDriver
        options = webdriver.ChromeOptions()
        service = webdriver.ChromeService("/opt/chromedriver")

        options.binary_location = '/opt/chrome/chrome'
        options.add_argument("--headless")
        options.add_argument('--no-sandbox')
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280x1696")
        options.add_argument("--single-process")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-dev-tools")
        options.add_argument("--no-zygote")
        options.add_argument(f"--user-data-dir={mkdtemp()}")
        options.add_argument(f"--data-path={mkdtemp()}")
        options.add_argument(f"--disk-cache-dir={mkdtemp()}")
        options.add_argument("--remote-debugging-port=9222")

        driver = webdriver.Chrome(options=options, service=service)

        # create a monitor class instance
        monitor = Monitor(driver)

        # 1. Open the provided URL in the browser
        is_available, screenshot_key = monitor.get_page_availability(url)

        # 2. Check Page Load Time
        page_load_time = monitor.get_page_load_time()
        
        # 3. Check for console errors
        console_errors = monitor.check_console_errors()

        # 4. Fetch all links on the page to Check external links for being broken
        links = driver.find_elements(by=By.TAG_NAME, value="a")
        link_texts = [link.get_attribute('href') for link in links if link.get_attribute('href').strip()]

        # get domain from event url so that we can separate external and internal url by comparing
        website_domain = extract_domain_from_url(url)

        # Separate External from internal urls/sitemaps.xml
        external_urls = get_external_url(link_texts, website_domain)

        # Ping all the external url
        external_broken_links = monitor.ping_external_url(external_urls)

        logs = {
            'site-available': is_available,
            'screenshot_url': f'https://{os.environ["S3_BUCKET_NAME"]}.s3.amazonaws.com/{screenshot_key}',
            'page-load-time': page_load_time,
            'console-logs': console_errors,
            'external-broken-link': external_broken_links,
            'links-texts': link_texts
        }

        # Upload logs to S3
        timestamp = int(time.time() * 1000)
        key = f'Monitoring-logs-{timestamp}.json'
        upload_logs_to_s3(logs, os.environ['S3_BUCKET_NAME'], key)

        return {
            'statusCode': 200,
            'body': 'Success',
            'logs': logs
        }

    finally:
        # Close the browser in the finally block to ensure cleanup
        if driver:
            driver.quit()