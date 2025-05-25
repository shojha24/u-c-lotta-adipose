from bs4 import BeautifulSoup
import requests
from datetime import datetime
import json

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

    def parse_hall_hrs(self):
        self.fetch_page()
        
        day_of_week = datetime.now().strftime("%A").lower()[0:3]  # Get the first three letters of the current day of the week

        # check if hours have already been parsed for this day of the week: halls -> location -> hours -> day of week
        if ("drey" in self.data["halls"]) and day_of_week in self.data["halls"]["drey"]["hours"]:
            print(f"Hours for {day_of_week} already parsed.")
        
        schedule_table = self.curr_soup.find('table', {'class': 'dining-hours-table'})
        
        # finds the first link tag in the table (so basically the first location)
        iter_elem = schedule_table.find('a', href=True)

        while iter_elem.find_next("td") is not None:
            if iter_elem.name == 'a':
                loc_name = iter_elem.text.strip()

                if loc_name not in self.data["halls"] and loc_name in names_to_abbr:
                    loc_name = names_to_abbr[loc_name]
                    loc_url = iter_elem['href']
                    self.data["halls"][loc_name] = {}
                    self.data["halls"][loc_name]["link"] = loc_url
                    iter_elem = iter_elem.find_next("td")
                else:
                    iter_elem = iter_elem.find_next("a", href=True)

            if iter_elem.name == 'td':
                self.data["halls"][loc_name]["hours"] = {}
                self.data["halls"][loc_name]["hours"][day_of_week] = {}
                self.data["halls"][loc_name]["hours"][day_of_week]["breakfast"] = iter_elem.text.strip()
                
                iter_elem = iter_elem.find_next("td")
                self.data["halls"][loc_name]["hours"][day_of_week]["lunch"] = iter_elem.text.strip()
                
                iter_elem = iter_elem.find_next("td")
                self.data["halls"][loc_name]["hours"][day_of_week]["dinner"] = iter_elem.text.strip()
                
                iter_elem = iter_elem.find_next("td")
                self.data["halls"][loc_name]["hours"][day_of_week]["ext_dinner"] = iter_elem.text.strip()
                
                iter_elem = iter_elem.find_next("a", href=True)
    
    def parse_truck_hrs(self):
        self.fetch_page("trucks")

        week_of = self.curr_soup.find('h2', {'class': 'wp-block-heading alignwide'}).text.strip()[41:]

        if "week_of" in self.data["trucks"] and self.data["trucks"]["week_of"] == week_of:
            print(f"Truck hours for week of {week_of} already parsed.")
            return
        
        self.data["trucks"]["week_of"] = week_of

        headings = self.curr_soup.find_all('h3', {'class': 'wp-block-heading'})
        for heading in headings:
            loc_name = heading.text.strip().lower()
            if loc_name not in self.data["trucks"]:
                self.data["trucks"][loc_name] = {}

            table_body = heading.find_next("tbody")
            for child in table_body.children:
                elems = child.find_all('td')
                self.data["trucks"][loc_name][elems[0].text.strip().lower()[0:3]] = {
                    "5 p.m. – 8:30 p.m.": elems[1].text.strip(),
                    "0 p.m. – 12 a.m.": elems[2].text.strip()
                }

    """def parse_hall_menus(self, halls):
        for hall in halls:
            
            hall_url = self.data["halls"][hall]["link"]
            try:
                response = requests.get(hall_url)
                response.raise_for_status()
                hall_soup = BeautifulSoup(response.content, 'lxml')
                
                menu_items = hall_soup.find_all('div', class_='menu-item')
                self.data["halls"][hall]["menu"] = [item.text.strip() for item in menu_items]
            except requests.RequestException as e:
                print(f"Error fetching menu for {hall}: {e}")"""

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
    "trucks": "https://dining.ucla.edu/meal-swipe-exchange/"
}

names_to_abbr = {
    "Bruin Plate": "b-plate",
    "De Neve Dining": "de-neve",
    "Epicuria at Covel": "epic-covel",
    "Epicuria at Ackerman": "epic-ackerman",
    "The Drey": "drey",
    "The Study at Hedrick": "study",
    "Rendezvous": "rende",
    "Bruin Caf\u00e9": "b-cafe",
    "Caf\u00e9 1919": "cafe-1919",
    "Spice Kitchen": "feast"
}

testScraper = Scraper(urls)
testScraper.fetch_page()
testScraper.parse_hall_hrs()
testScraper.parse_truck_hrs()
testScraper.save_data()


"""
<tr><td class="has-text-align-left" data-align="left"><strong><strong><strong>Sun, May 25 </strong></strong></strong></td><td></td><td>Habibi Shack</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong><strong>Mon,</strong></strong></strong> <strong><strong><strong>May 26 </strong></strong></strong></td><td>Perro 1-10 Tacos</td><td>Don Pollón</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong><strong>Tue, May 27</strong></strong></strong></td><td>Heritage Kitchen</td><td>Rice Balls of Fire</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong><strong>Wed, May 28</strong></strong></strong></td><td>Uncle Al’s Barbeque</td><td>Perro 1-10 Tacos</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong>T<strong>hu, May 29</strong></strong></strong></td><td>Kalamaki Greek Street Food</td><td>8E8 Thai Street Food</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong><strong>Fri, May 30</strong></strong></strong></td><td>Vchos Pupusería Moderna</td><td>El Gallo Yucateco</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong><strong><strong>Sat, May 24</strong></strong></strong></strong></td><td></td><td>Aloha Fridays</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong><strong><strong><strong>Sun, May 25</strong></strong></strong></strong></strong></td><td></td><td></td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong>Mon, <strong><strong><strong><strong><strong>May 26</strong></strong></strong></strong></strong></strong></strong></td><td></td><td>BittieBitez Mini-Donuts</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong>Tue, <strong><strong><strong>May 27</strong></strong></strong></strong></strong></td><td>Cerda vega Tacos</td><td>BittieBitez Mini-Donuts</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong>Wed, <strong><strong><strong>May 28</strong></strong></strong></strong></strong></td><td>The Taco Cartel</td><td>Salpicón</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong><strong>T<strong>hu, May 29</strong></strong></strong></strong></td><td>Pinch of Flavor</td><td>Salpicón</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong>Fri, <strong><strong><strong>May 30</strong></strong></strong></strong></strong></td><td>Pinch of Flavor</td><td>Salpicón</td></tr>
<tr><td class="has-text-align-left" data-align="left"><strong><strong><strong><strong><strong>Sat, May 24</strong></strong></strong></strong></strong></td><td></td><td></td></tr>
"""