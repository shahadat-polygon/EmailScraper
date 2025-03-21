import requests
from bs4 import BeautifulSoup
import re
import csv

# Function to scrape emails from a website
def scrape_emails(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = soup.get_text()

        # Regular expression to find email addresses
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = set(re.findall(email_pattern, text))  # Using set to avoid duplicates
        return emails
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return set()


# Main function to process websites from CSV
def main():
    input_csv = "assets/email_scrap.csv"  # Your input CSV file
    output_csv = "emails_output.csv"  # New file for results

    # Read websites from CSV
    websites = []
    with open(input_csv, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        # Assuming the CSV has a column named "website" with URLs
        websites = [row["website"] for row in reader if row["website"].startswith("http")]

    # Scrape emails and store results
    results = []
    for url in websites:
        print(f"Scraping {url}...")
        emails = scrape_emails(url)
        results.append({"website": url, "emails": ", ".join(emails) if emails else "No emails found"})

    # Write results to a new CSV
    with open(output_csv, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = ["website", "emails"]
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Scraping complete. Results saved to {output_csv}")


if __name__ == "__main__":
    main()