from bs4 import BeautifulSoup
import requests
from datetime import datetime
import json

urls = {
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
}

class Scraper:
    def __init__(self, urls):
        self.urls = urls
        self.curr_soup = None
        self.load_data()

    def save_data(self, filename='dining_info.json'):
        try:
            with open(filename, 'w') as file:
                json.dump(self.data, file, indent=4)
            print(f"Data saved to {filename}")
        except IOError as e:
            print(f"Error saving data to {filename}: {e}")

    def load_data(self, filename='dining_info.json'):
        try:
            with open(filename, 'r') as file:
                self.data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading data from {filename}: {e}")
            self.data = {
                "halls": {},
                "trucks": {},
                "ASUCLA": {}
            }

    def print_data(self):
        print(self.data)

    def fetch_page(self, key='hours'):
        try:
            response = requests.get(self.urls[key])
            response.raise_for_status()
            self.curr_soup = BeautifulSoup(response.content, 'lxml')
        except requests.RequestException as e:
            print(f"Error fetching page: {e}")
    
    def parse_hours(self):
        if self.curr_soup is None:
            print("No page content to parse.")
        
        day_of_week = datetime.now().strftime("%A").lower()

        # check if hours have already been parsed for this day of the week: halls -> location -> hours -> day of week
        if ("The Drey" in self.data["halls"]) and day_of_week in self.data["halls"]["The Drey"]["hours"]:
            print(f"Hours for {day_of_week} already parsed.")
        
        schedule_table = self.curr_soup.find('table', {'class': 'dining-hours-table'})
        
        # finds the first link tag in the table (so basically the first location)
        iter_elem = schedule_table.find('a', href=True)

        while iter_elem.find_next("td") is not None:
            if iter_elem.name == 'a':
                location_name = iter_elem.text.strip()

                if location_name not in self.data["halls"]:
                    location_url = iter_elem['href']
                    self.data["halls"][location_name] = {}
                    self.data["halls"][location_name]["link"] = location_url

                iter_elem = iter_elem.find_next("td")

            if iter_elem.name == 'td':
                self.data["halls"][location_name]["hours"] = {}
                self.data["halls"][location_name]["hours"][day_of_week] = {}
                self.data["halls"][location_name]["hours"][day_of_week]["breakfast"] = iter_elem.text.strip()
                
                iter_elem = iter_elem.find_next("td")
                self.data["halls"][location_name]["hours"][day_of_week]["lunch"] = iter_elem.text.strip()
                
                iter_elem = iter_elem.find_next("td")
                self.data["halls"][location_name]["hours"][day_of_week]["dinner"] = iter_elem.text.strip()
                
                iter_elem = iter_elem.find_next("td")
                self.data["halls"][location_name]["hours"][day_of_week]["ext_dinner"] = iter_elem.text.strip()
                
                iter_elem = iter_elem.find_next("a", href=True)

testScraper = Scraper(urls)
testScraper.fetch_page()
testScraper.parse_hours()
testScraper.save_data()
testScraper.print_data()