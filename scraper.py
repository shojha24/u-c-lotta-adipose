from bs4 import BeautifulSoup
import boto3
from io import StringIO
import requests
from datetime import datetime, timedelta
import json
import re
from typing import Dict, List, Optional, Any
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UCLADiningScraper:
    """
    A comprehensive scraper for UCLA dining information including hours, menus, and nutrition data.
    Designed for both file storage and API integration.
    """
    
    DINING_URLS = {
        "hours": "https://dining.ucla.edu/dining-locations/",
        "b-plate": "https://dining.ucla.edu/bruin-plate/",
        "de-neve": "https://dining.ucla.edu/de-neve-dining/",
        "epic-covel": "https://dining.ucla.edu/epicuria-at-covel/", 
        "epic-ackerman": "https://dining.ucla.edu/epicuria-at-ackerman/",
        "drey": "https://dining.ucla.edu/the-drey/",
        "study": "https://dining.ucla.edu/the-study-at-hedrick/",
        "rende": "https://dining.ucla.edu/rendezvous/",
        "b-cafe": "https://dining.ucla.edu/bruin-cafe/",
        "cafe-1919": "https://dining.ucla.edu/cafe-1919/",
        "feast": "https://dining.ucla.edu/spice-kitchen/",
        "trucks": "https://dining.ucla.edu/meal-swipe-exchange/"
    }
    
    LOCATION_NAME_MAPPING = {
        "Bruin Plate": "b-plate",
        "Sproul Dining": "b-plate",
        "De Neve Dining": "de-neve",
        "Epicuria at Covel": "epic-covel",
        "Covel Dining": "epic-covel",
        "Epicuria at Ackerman": "epic-ackerman",
        "The Drey": "drey",
        "The Study at Hedrick": "study",
        "Rendezvous": "rende",
        "Bruin Café": "b-cafe",
        "Café 1919": "cafe-1919",
        "Spice Kitchen at Bruin Bowl": "feast"
    }

    def __init__(self):
        self.current_soup: Optional[BeautifulSoup] = None
        self.dining_data = self._initialize_dining_data()
        
    def _initialize_dining_data(self) -> Dict[str, Any]:
        """Initialize the main dining data structure."""
        return {
            "halls": {},
            "trucks": {},
            "ASUCLA": {},
            "items": {},
            "last_updated": None
        }

    # Data Management Methods
    def save_to_local(self, dining_filename: str = 'dining_info.json') -> bool:
        """Save data to JSON files with error handling."""
        try:
            self.dining_data["last_updated"] = datetime.now().isoformat()

            with open(dining_filename, 'w') as file:
                json.dump(self.dining_data, file, indent=4)
                            
            logger.info(f"Data successfully saved to {dining_filename}")
            return True
            
        except IOError as e:
            logger.error(f"Error saving data: {e}")
            return False
        
    def save_to_s3(self, bucket_name: str = 'u-c-lotta-adipose', 
                     dining_key: str = 'dining_info.json') -> bool:
        """Save data to S3 using boto3."""
        try:
            # Install: pip install boto3
            self.dining_data["last_updated"] = datetime.now().isoformat()
            s3_client = boto3.client('s3')
            
            # Convert to JSON and upload dining data
            dining_buffer = StringIO()
            json.dump(self.dining_data, dining_buffer, indent=4)
            s3_client.put_object(
                Bucket=bucket_name,
                Key=dining_key,
                Body=dining_buffer.getvalue(),
                ContentType='application/json'
            )
            
            logger.info(f"Data successfully saved to S3: {bucket_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving to S3: {e}")
            return False

    def load_from_local(self, dining_filename: str = 'dining_info.json') -> bool:
        """Load from local files."""

        try:
            with open(dining_filename, 'r') as file:
                self.dining_data = json.load(file)
                
        except FileNotFoundError as e:
            logger.error(f"Error loading local files: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from local files: {e}")
            return False
            
        logger.info("Data successfully loaded from local files")
        return True

    def load_from_s3(self, bucket_name: str = 'u-c-lotta-adipose', 
                        dining_key: str = 'dining_info.json') -> bool:
        """Load from S3 using simple boto3 approach."""
        import boto3
        
        s3_client = boto3.client('s3')
        
        try:
            # Load dining data
            dining_response = s3_client.get_object(Bucket=bucket_name, Key=dining_key)
            self.dining_data = json.loads(dining_response['Body'].read().decode('utf-8'))
                        
            logger.info("Data successfully loaded from S3")
            return True
            
        except Exception as e:
            logger.warning(f"Could not load from S3: {e}")
            return False
        
        
    # API Integration Methods
    def get_dining_data(self) -> Dict[str, Any]:
        """Get complete dining data for API consumption."""
        return self.dining_data.copy()
    
    def get_menu_items(self) -> Dict[str, Any]:
        """Get complete menu items data for API consumption."""
        return self.dining_data["items"].copy()
    
    def get_hall_data(self, hall_name: str) -> Optional[Dict[str, Any]]:
        """Get specific hall data for API consumption."""
        return self.dining_data["halls"].get(hall_name)
    
    def get_item_data(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get specific menu item data for API consumption."""
        return self.menu_items["items"].get(item_id)

    # Web Scraping Methods
    def _fetch_page(self, url_key: str = 'hours') -> bool:
        """Fetch and parse a webpage."""
        try:
            response = requests.get(self.DINING_URLS[url_key])
            response.raise_for_status()
            self.current_soup = BeautifulSoup(response.content, 'lxml')
            return True
        except requests.RequestException as e:
            logger.error(f"Error fetching page {url_key}: {e}")
            return False

    def scrape_dining_hours(self) -> bool:
        """Scrape dining hall hours for the current day."""
        if not self._fetch_page('hours'):
            return False
            
        current_day = datetime.now().strftime("%A").lower()[:3]
        
        # Check if hours already exist for today
        if self._hours_already_scraped(current_day):
            logger.info(f"Hours for {current_day} already exist")
            return True
        
        try:
            schedule_table = self.current_soup.find('table', {'class': 'dining-hours-table'})
            if not schedule_table:
                logger.error("Could not find dining hours table")
                return False
                
            self._parse_dining_hours_table(schedule_table, current_day)
            logger.info("Successfully scraped dining hours")
            return True
            
        except Exception as e:
            logger.error(f"Error parsing dining hours: {e}")
            return False

    def _hours_already_scraped(self, day: str) -> bool:
        """Check if hours have already been scraped for the given day."""
        return (
            "drey" in self.dining_data["halls"] and 
            "hours" in self.dining_data["halls"]["drey"] and 
            day in self.dining_data["halls"]["drey"]["hours"]
        )

    def _parse_dining_hours_table(self, table: BeautifulSoup, day: str) -> None:
        """Parse the dining hours table and extract information."""
        current_element = table.find('a', href=True)
        
        while current_element and current_element.find_next("td"):
            if current_element.name == 'a':
                location_name = current_element.text.strip()
                
                if location_name in self.LOCATION_NAME_MAPPING:
                    abbreviated_name = self.LOCATION_NAME_MAPPING[location_name]
                    location_url = current_element['href']
                    
                    if abbreviated_name not in self.dining_data["halls"]:
                        self.dining_data["halls"][abbreviated_name] = {
                            "link": location_url,
                            "hours": {}
                        }
                    
                    # Parse hours for this location
                    current_element = self._parse_location_hours(
                        current_element, abbreviated_name, day
                    )
                else:
                    current_element = current_element.find_next("a", href=True)

    def _parse_location_hours(self, element: BeautifulSoup, location: str, day: str) -> BeautifulSoup:
        """Parse hours for a specific location."""
        element = element.find_next("td")
        
        if not element:
            return None
            
        self.dining_data["halls"][location]["hours"][day] = {
            "breakfast": element.text.strip(),
            "lunch": element.find_next("td").text.strip(),
            "dinner": element.find_next("td").find_next("td").text.strip(),
            "ext_dinner": element.find_next("td").find_next("td").find_next("td").text.strip()
        }
        
        return element.find_next("td").find_next("td").find_next("td").find_next("a", href=True)

    def scrape_food_truck_hours(self) -> bool:
        """Scrape food truck hours and schedules."""
        if not self._fetch_page("trucks"):
            return False
            
        try:
            week_header = self.current_soup.find('h2', {'class': 'wp-block-heading alignwide'})
            if not week_header:
                logger.error("Could not find week header for food trucks")
                return False
                
            current_week = week_header.text.strip()[41:]
            
            # Check if truck hours already exist for this week
            if (
                "week_of" in self.dining_data["trucks"] and 
                self.dining_data["trucks"]["week_of"] == current_week
            ):
                logger.info(f"Truck hours for week of {current_week} already exist")
                return True
            
            self.dining_data["trucks"]["week_of"] = current_week
            self._parse_truck_schedules()
            
            logger.info("Successfully scraped food truck hours")
            return True
            
        except Exception as e:
            logger.error(f"Error scraping food truck hours: {e}")
            return False

    def _parse_truck_schedules(self) -> None:
        """Parse food truck schedules from the webpage."""
        headings = self.current_soup.find_all('h3', {'class': 'wp-block-heading'})
        
        for heading in headings:
            location_name = heading.text.strip().lower()
            
            if location_name not in self.dining_data["trucks"]:
                self.dining_data["trucks"][location_name] = {}

            table_body = heading.find_next("tbody")
            if table_body:
                for row in table_body.children:
                    cells = row.find_all('td')
                    if len(cells) >= 3:
                        day = cells[0].text.strip().lower()[:3]
                        self.dining_data["trucks"][location_name][day] = {
                            "5 p.m. – 8:30 p.m.": cells[1].text.strip(),
                            "10 p.m. – 12 a.m.": cells[2].text.strip()
                        }

    def scrape_hall_menus(self, halls: Optional[List[str]] = None) -> bool:
        """Scrape menus for specified dining halls."""
        if halls is None:
            halls = [
                "b-plate", "de-neve", "epic-covel", "epic-ackerman", 
                "drey", "study", "rende", "b-cafe", "cafe-1919", "feast"
            ]
        
        success_count = 0
        for hall in halls:
            dates_to_scrape = [
                (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d") 
                for i in range(-1, 6)
            ]
            for date in dates_to_scrape:
                if self._scrape_single_hall_menu(hall, date):
                    success_count += 1
        
        success_count /= 7

        logger.info(f"Successfully scraped menus for {success_count}/{len(halls)} halls")
        return success_count > 0

    def _scrape_single_hall_menu(self, hall: str, date: str = datetime.now().strftime("%Y-%m-%d")) -> bool:
        """Scrape menu for a single dining hall."""
        if hall not in self.dining_data["halls"]:
            logger.warning(f"Hall {hall} not found in dining data")
            return False
            
        hall_url = self.dining_data["halls"][hall]["link"]
        
        try:
            response = requests.get(f"{hall_url}/?date={date}")
            response.raise_for_status()
            hall_soup = BeautifulSoup(response.content, 'lxml')
            
            self._parse_hall_menu_sections(hall_soup, hall, date)
            logger.info(f"Successfully scraped menu for {hall}")
            return True
            
        except requests.RequestException as e:
            logger.error(f"Error fetching menu for {hall}: {e}")
            return False

    def _parse_hall_menu_sections(self, soup: BeautifulSoup, hall: str, day: str) -> None:
        """Parse menu sections for a dining hall."""
        
        # Initialize menu structure
        if "menu" not in self.dining_data["halls"][hall]:
            self.dining_data["halls"][hall]["menu"] = {}
        if day not in self.dining_data["halls"][hall]["menu"]:
            self.dining_data["halls"][hall]["menu"][day] = {}
            self.dining_data["halls"][hall]["menu"][day]["open"] = True
        else:
            logger.info(f"Menu for {hall} on {day} already exists")
            return
        
        closed_today = soup.find('p', {'class': 'dining-status'})
        if closed_today:
            logger.info(f"{hall} is closed today")
            self.dining_data["halls"][hall]["menu"][day] = {"open": False}
            return
        
        menu_sections = (
            soup.find_all('div', {'id': 'breakfastmenu'}) +
            soup.find_all('div', {'id': 'lunchmenu'}) +
            soup.find_all('div', {'id': 'dinnermenu'})
        )
        
        for section in menu_sections:
            meal_type = ''.join(section.find_next('h2').text.split()).lower()
            self.dining_data["halls"][hall]["menu"][day][meal_type] = {}
            
            container = section.find_next('div', {'class': 'at-a-glance-menu__dining-location'})
            if container:
                self._parse_menu_container(container, hall, day, meal_type)

    def _parse_menu_container(self, container: BeautifulSoup, hall: str, day: str, meal_type: str) -> None:
        """Parse individual menu container sections."""
        sections = [content for content in container.contents if content.name == 'div']
        
        for section in sections:
            section_header = section.find('h2')
            if not section_header:
                continue
                
            section_name = ''.join(section_header.text.strip().lower().split())
            
            section_list = section.find_next('div', {'class': 'recipe-list'})
            if not section_list:
                continue
                
            menu_items = section_list.find_all('section', {'class': 'recipe-card'})
            item_links = [
                f"https://dining.ucla.edu{item.find('a', href=True)['href']}" 
                for item in menu_items if item.find('a', href=True)
            ]
            item_ids = [
                re.search(r'(\d+)', link).group(0) 
                for link in item_links if re.search(r'(\d+)', link)
            ]
            
            self.dining_data["halls"][hall]["menu"][day][meal_type][section_name] = item_ids
            
            # Scrape individual item information
            for item_id, item_link in zip(item_ids, item_links):
                self._scrape_menu_item(item_id, item_link)

    def _scrape_menu_item(self, item_id: str, url: str) -> bool:
        """Scrape nutrition information for a menu item."""
        # Check if item already exists
        if item_id in self.dining_data["items"]:
            logger.debug(f"Item {item_id} already exists")
            return True
            
        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')
            
            item_info = self._parse_standard_item(soup)
            if item_info:
                self.dining_data["items"][item_id] = item_info
                return True
            else:
                return self._scrape_custom_item(item_id, url, soup)
                
        except Exception as e:
            logger.error(f"Error scraping item {item_id}: {e}")
            return False

    def _parse_standard_item(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parse a standard menu item with nutrition facts."""
        try:
            item_info = {}
            
            # Get item name
            name_element = soup.find('h2', {'class': 'headline-text__lg'})
            if not name_element:
                return None
            item_info["name"] = name_element.text.strip()
            
            # Get dietary labels
            content_div = soup.find('div', {'class': 'single-menu-page-content'})
            if content_div:
                icons = content_div.find_all('img')
                labels = []
                for icon in icons:
                    src = icon.get('src', '')
                    match = re.search(r'([^\/.]*)\.svg', src)
                    if match:
                        labels.append(match.group(1))
                item_info["labels"] = labels
            
            # Get nutrition facts
            nutrition_section = soup.find('div', {'id': 'nutrition'})
            if not nutrition_section:
                return None
                
            # Serving size
            serving_element = soup.find('strong')
            if serving_element and serving_element.next_sibling:
                item_info['serving_size'] = serving_element.next_sibling.strip()
            
            # Calories
            calories_element = nutrition_section.find('p', {'class': 'single-calories'})
            if calories_element:
                calories_span = calories_element.find('span')
                if calories_span and calories_span.next_sibling:
                    item_info['calories'] = calories_span.next_sibling.strip()
            
            # Other nutrition facts
            nutrition_tags = nutrition_section.find_all('span')[1:]
            for tag in nutrition_tags:
                if tag.next_sibling:
                    tag_value = tag.next_sibling.strip()
                    percent_element = tag.find_next('td')
                    percent_value = percent_element.text.strip() if percent_element else None
                    
                    if tag_value:
                        item_info[tag.text.strip().lower()] = [tag_value, percent_value]
            
            return item_info
            
        except Exception:
            return None

    def _scrape_custom_item(self, item_id: str, url: str, soup: BeautifulSoup) -> bool:
        """Handle custom/complex items with ingredients."""
        try:
            item_info = {}
            
            name_element = soup.find("h2", "headline-text__lg")
            if not name_element:
                return False
            item_info["name"] = name_element.text.strip()
            
            item_info["ingredients"] = {}
            ingredient_sections = soup.find_all("div", {"class": "complex-ingredient-group"})
            
            for section in ingredient_sections:
                header = section.find("h4")
                if not header:
                    continue
                    
                section_label = header.text.strip()
                item_info["ingredients"][section_label] = []
                
                ingredients = section.find_all("li")
                for ingredient in ingredients:
                    link_element = ingredient.find("a", href=True)
                    if link_element:
                        ingredient_link = link_element['href']
                        ingredient_match = re.search(r'(\d+)', ingredient_link)
                        if ingredient_match:
                            ingredient_id = ingredient_match.group(0)
                            item_info["ingredients"][section_label].append(ingredient_id)
                            # Recursively scrape ingredient
                            self._scrape_menu_item(ingredient_id, f"https://dining.ucla.edu{ingredient_link}")
            
            self.dining_data["items"][item_id] = item_info
            return True
            
        except Exception as e:
            logger.error(f"Error parsing custom item {item_id}: {e}")
            return False

    # Main execution methods
    def scrape_all_data(self) -> bool:
        """Scrape all available dining data."""
        logger.info("Starting comprehensive data scraping...")
        
        success_flags = [
            self.scrape_dining_hours(),
            self.scrape_food_truck_hours(),
            self.scrape_hall_menus()
        ]
        
        overall_success = all(success_flags)
        logger.info(f"Data scraping completed. Success: {overall_success}")
        return overall_success

    def update_and_save(self) -> bool:
        """Update all data and save to files."""
        self.load_from_s3()  # Load existing data first
        success = self.scrape_all_data()
        if success:
            return self.save_to_s3()
        return False


# Example usage and API integration
def main():
    """Example usage of the scraper."""
    scraper = UCLADiningScraper()
    
    # For file-based usage
    if scraper.update_and_save():
        print("Successfully updated and saved dining data")
    
    return scraper

if __name__ == "__main__":
    main()
