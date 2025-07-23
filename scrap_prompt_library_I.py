import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin, urlparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ChatGPTPromptsScraper:
    def __init__(self, base_url="https://gptbot.io"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.prompts_data = []
        
    def get_page(self, url):
        """Get page content with error handling"""
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None
    
    def extract_prompt_cards(self, html_content):
        """Extract prompt cards from the main page"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all prompt cards based on the HTML structure from the provided examples
        cards = soup.find_all('div', class_=lambda x: x and 'border bg-card text-card-foreground shadow-sm' in x)
        
        prompt_cards = []
        
        for card in cards:
            try:
                # Extract category
                category_elem = card.find('div', class_=lambda x: x and 'inline-flex items-center' in x and 'text-ui-badge-text' in x)
                category = category_elem.get_text(strip=True) if category_elem else "Unknown"
                
                # Extract title and link
                title_link_elem = card.find('a', class_='transition-colors')
                if title_link_elem:
                    title = title_link_elem.find('h3').get_text(strip=True) if title_link_elem.find('h3') else "Unknown"
                    link = title_link_elem.get('href')
                    full_link = urljoin(self.base_url, link) if link else None
                else:
                    title = "Unknown"
                    full_link = None
                
                # Extract preview text if available
                preview_elem = card.find('p', class_='text-[15px] text-muted-foreground')
                preview = preview_elem.get_text(strip=True) if preview_elem else ""
                
                if full_link:
                    prompt_cards.append({
                        'category': category,
                        'title': title,
                        'link': full_link,
                        'preview': preview
                    })
                    
            except Exception as e:
                logger.error(f"Error extracting card data: {str(e)}")
                continue
        
        return prompt_cards
    
    def extract_prompt_content(self, prompt_url):
        """Extract full prompt content from individual prompt page"""
        html_content = self.get_page(prompt_url)
        if not html_content:
            return None
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        try:
            # Look for the content in the article or prose section
            content_elem = soup.find('article', {'id': 'content'})
            if not content_elem:
                content_elem = soup.find('div', class_=lambda x: x and 'prose' in x)
            
            if content_elem:
                # Extract all text content, preserving structure
                content = content_elem.get_text(separator='\n', strip=True)
                
                # Clean up the content
                content = re.sub(r'\n{3,}', '\n\n', content)  # Remove excessive newlines
                content = content.strip()
                
                return content
            else:
                logger.warning(f"Could not find content element in {prompt_url}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting content from {prompt_url}: {str(e)}")
            return None
    
    def scrape_all_prompts(self):
        """Main scraping method"""
        logger.info("Starting to scrape ChatGPT prompts...")
        
        # Get main page
        main_url = f"{self.base_url}/chatgpt-prompts"
        html_content = self.get_page(main_url)
        
        if not html_content:
            logger.error("Failed to get main page content")
            return None
        
        # Extract all prompt cards
        prompt_cards = self.extract_prompt_cards(html_content)
        logger.info(f"Found {len(prompt_cards)} prompt cards")
        
        # Process each prompt
        for i, card in enumerate(prompt_cards, 1):
            logger.info(f"Processing prompt {i}/{len(prompt_cards)}: {card['title']}")
            
            # Get full content
            full_content = self.extract_prompt_content(card['link'])
            
            # Add to results
            prompt_data = {
                'category': card['category'],
                'title': card['title'],
                'link': card['link'],
                'preview': card['preview'],
                'full_content': full_content if full_content else card['preview']
            }
            
            self.prompts_data.append(prompt_data)
            
            # Be respectful to the server
            time.sleep(1)
        
        logger.info(f"Completed scraping {len(self.prompts_data)} prompts")
        return self.prompts_data
    
    def save_to_csv(self, filename='chatgpt_prompts.csv'):
        """Save scraped data to CSV file"""
        if not self.prompts_data:
            logger.error("No data to save")
            return False
        
        df = pd.DataFrame(self.prompts_data)
        df.to_csv(filename, index=False, encoding='utf-8')
        logger.info(f"Data saved to {filename}")
        return True
    
    def get_dataframe(self):
        """Return pandas DataFrame of scraped data"""
        return pd.DataFrame(self.prompts_data)

# Usage example
if __name__ == "__main__":
    scraper = ChatGPTPromptsScraper()
    
    # Scrape all prompts
    prompts_data = scraper.scrape_all_prompts()
    
    if prompts_data:
        # Save to CSV
        scraper.save_to_csv('chatgpt_prompts.csv')
        
        # Display summary
        df = scraper.get_dataframe()
        print(f"\nScraping Summary:")
        print(f"Total prompts scraped: {len(df)}")
        print(f"Categories found: {df['category'].nunique()}")
        print(f"\nCategory distribution:")
        print(df['category'].value_counts())
        
        # Show first few rows
        print(f"\nFirst 5 prompts:")
        print(df[['category', 'title']].head())
    else:
        print("Failed to scrape prompts")
