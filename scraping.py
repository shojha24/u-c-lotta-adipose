from bs4 import BeautifulSoup
import requests
from datetime import datetime
import json
import re

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


class Scraper:
    def __init__(self, urls=urls):
        self.urls = urls
        self.curr_soup = None
        self.error_urls = []
        self.load_data()
        self.names_to_abbr = {
            "Bruin Plate": "b-plate",
            "De Neve Dining": "de-neve",
            "Epicuria at Covel": "epic-covel",
            "Epicuria at Ackerman": "epic-ackerman",
            "The Drey": "drey",
            "The Study at Hedrick": "study",
            "Rendezvous": "rende",
            "Bruin Caf\u00e9": "b-cafe",
            "Caf\u00e9 1919": "cafe-1919",
            "Spice Kitchen at Bruin Bowl": "feast"
        }
        self.labels = {'sesame', 'peanut', 'vegetarian', 'high-carbon', 'vegan', 
                       'soy', 'wheat', 'tree-nuts', 'dairy', 'gluten', 'alcohol', 
                       'halal', 'eggs', 'low-carbon', 'crustacean-shellfish', 'fish'}

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
            return
        
        schedule_table = self.curr_soup.find('table', {'class': 'dining-hours-table'})
        
        # finds the first link tag in the table (so basically the first location)
        iter_elem = schedule_table.find('a', href=True)

        while iter_elem.find_next("td") is not None:
            if iter_elem.name == 'a':
                loc_name = iter_elem.text.strip()

                if loc_name not in self.data["halls"] and loc_name in self.names_to_abbr:
                    loc_name = self.names_to_abbr[loc_name]
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

    def parse_hall_menus(self, halls=["b-plate", "de-neve", "epic-covel", "epic-ackerman", "drey", "study", "rende", "b-cafe", "cafe-1919", "feast"]):
        for hall in halls:
            
            hall_url = self.data["halls"][hall]["link"]

            day_of_week = datetime.now().strftime("%A").lower()[0:3]

            try:
                response = requests.get(hall_url)
                response.raise_for_status()
                hall_soup = BeautifulSoup(response.content, 'lxml')
                
                headings = hall_soup.find_all('div', {'id': 'breakfastmenu'}) + hall_soup.find_all('div', {'id': 'lunchmenu'}) + hall_soup.find_all('div', {'id': 'dinnermenu'})
                
                for heading in headings:
                    meal_type = ''.join(heading.find_next('h2').text.split()).lower()
                    if "menu" not in self.data["halls"][hall]:
                        self.data["halls"][hall]["menu"] = {}
                    if day_of_week not in self.data["halls"][hall]["menu"]:
                        self.data["halls"][hall]["menu"][day_of_week] = {}
                    self.data["halls"][hall]["menu"][day_of_week][meal_type] = {}

                    container = heading.find_next('div', {'class': 'at-a-glance-menu__dining-location'})
                    sections = [contents for contents in container.contents if contents.name == 'div']
                    for section in sections:
                        section_name = ''.join(section.find('h2').text.strip().lower().split())

                        section_list = section.find_next('div', {'class': 'recipe-list'})
                        menu_items = section_list.find_all('section', {'class': 'recipe-card'})
                        item_links = [f"https://dining.ucla.edu{item.find('a', href=True)['href']}"  for item in menu_items]
                        item_ids = [re.search(r'(\d+)', link).group(0) for link in item_links]
                        
                        self.data["halls"][hall]["menu"][day_of_week][meal_type][section_name] = item_ids

                        for i in range(len(item_links)):
                            self.parse_item_info(item_ids[i], item_links[i], menu_items[i])
                            
            except requests.RequestException as e:
                print(f"Error fetching menu for {hall}: {e}")


    def parse_item_info(self, id, url, item):
        item_info = {}

        # Load existing data
        try:
            with open('menu_items.json', 'r') as file:
                items_data = json.load(file)
                if items_data.get(id):
                    print(f"Nutrition info for recipe ID {id} already exists.")
                    return
        except (FileNotFoundError, json.JSONDecodeError):
            items_data = {}

        item_name = item.find('h3').text.strip()
        item_info["name"] = item_name
        item_icons = item.find_all('img')
        item_labels = [icon['title'].lower() for icon in item_icons]
        item_info["labels"] = item_labels

        try:
            response = requests.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'lxml')

            nutrition_facts = soup.find('div', {'id': 'nutrition'})

            serving_size_tag = soup.find('strong')
            serving_size = serving_size_tag.next_sibling.strip()
            item_info['serving_size'] = serving_size

            calories_tag = nutrition_facts.find('p', {'class': 'single-calories'}).find('span')
            calories = calories_tag.next_sibling.strip() if calories_tag.next_sibling else None
            item_info['calories'] = calories

            tags = nutrition_facts.find_all('span')[1:]
            for tag in tags:
                tag_val = tag.next_sibling.strip()
                percent_tag = tag.find_next('td').text.strip() if tag.find_next('td') else None
                if tag_val:
                    item_info[tag.text.strip().lower()] = [tag_val, percent_tag]

            # Save updated data - FIXED SECTION
            try:
                items_data[id] = item_info
                with open('menu_items.json', 'w') as file:  # Open in write mode AFTER loading data
                    json.dump(items_data, file, indent=4)
                print(f"Data saved to menu_items.json")
            except IOError as e:
                print(f"Error saving data to menu_items.json: {e}")
                    
        except Exception as e:
            print(f"URL: {url}")
            self.error_urls.append(url)
        
    



testScraper = Scraper(urls)
testScraper.fetch_page()
testScraper.parse_hall_hrs()
testScraper.parse_truck_hrs()
testScraper.parse_hall_menus()
testScraper.save_data()
print(testScraper.error_urls)

"""
{'link': 'https://dining.ucla.edu/bruin-plate/', 'hours': {'sun': {'breakfast': '7:00 a.m. - 10:00 a.m.', 'lunch': '11:30 a.m. - 2:00 p.m.', 'dinner': '5:00 p.m. - 9:00 p.m.', 'ext_dinner': 'Closed'}}}
{'link': 'https://dining.ucla.edu/de-neve-dining/', 'hours': {'sun': {'breakfast': '9 a.m. - 10:00 a.m.', 'lunch': '11:00 a.m. - 3:00 p.m.',  '11:00 a.m. - 3:00 p.m.', 'dinner': '5:00 p.m. - 9:00 p.m.', 'ext_dinner': '10:00 p.m. - 12:00 a.m.'}}}
{'link': 'https://dining.ucla.edu/epicuria-at-covel/', 'hours': {'sun': {'breakfast': 'Closed', 'lunch': 'Closed', 'dinner': 'Closed', 'ext_dinner': 'Closed'}}}
{'link': 'https://dining.ucla.edu/epicuria-at-ackerman/', 'hours': {'sun': {'breakfast': 'Closed', 'lunch': 'Closed', 'dinner': 'Closed', 'ext_dinner': 'Closed'}}}
{'link': 'https://dining.ucla.edu/the-drey/', 'hours': {'sun': {'breakfast': 'Closed', 'lunch': 'Closed', 'dinner': 'Closed', 'ext_dinner': 'Closed'}}}
{'link': 'https://dining.ucla.edu/the-study-at-hedrick/', 'hours': {'sun': {'breakfast': 'Closed', 'lunch': '11:00 a.m. - 3:00 p.m.', 'dinner': '5:00 p.m. - 9:00 p.m.', 'ext_dinner': '9:00 p.m. - 12:00 a.m.'}}}
{'link': 'https://dining.ucla.edu/rendezvous/', 'hours': {'sun': {'breakfast': 'Closed', 'lunch': '11:00 a.m. - 3:00 p.m.', 'dinner': '5:00 p.m. - 9:00 p.m.', 'ext_dinner': 'Closed'}}}
{'link': 'https://dining.ucla.edu/bruin-cafe/', 'hours': {'sun': {'breakfast': 'Closed', 'lunch': 'Closed', 'dinner': 'Closed', 'ext_dinner': 'Closed'}}}
{'link': 'https://dining.ucla.edu/cafe-1919/', 'hours': {'sun': {'breakfast': 'Closed', 'lunch': 'Closed', 'dinner': 'Closed', 'ext_dinner': 'Closed'}}}
{'link': 'https://dining.ucla.edu/spice-kitchen/', 'hours': {'sun': {'breakfast': 'Closed', 'lunch': 'Closed', 'dinner': 'Closed', 'ext_dinner': 'Closed'}}}"""