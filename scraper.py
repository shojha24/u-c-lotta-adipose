from bs4 import BeautifulSoup
try:
    import boto3
except ImportError:
    boto3 = None
from io import StringIO
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urljoin, urlparse, parse_qs
import base64
import gzip
import json
import os
import re
from typing import Dict, List, Optional, Any, Tuple
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PACIFIC_TZ = ZoneInfo("America/Los_Angeles")


class UCLADiningScraper:
    """
    A comprehensive scraper for UCLA dining information including hours, menus, and nutrition data.
    Designed for both file storage and API integration.
    """

    BASE_URL = "https://dining.ucla.edu/"
    DEFAULT_DATA_FILE = "dining-data.json"
    NUTRITION_CALC_API = "https://dining.ucla.edu/wp-content/plugins/custom-short-code/nutrition_calc_ajax.php"
    ACTIVITY_API = "https://dining.ucla.edu/wp-content/plugins/activity-meter/activity_ajax.php"

    GYM_URLS = {
        "b-fit": "https://recreation.ucla.edu/facilities/bfit",
        "wooden": "https://recreation.ucla.edu/facilities/jwc",
        "kinross": "https://recreation.ucla.edu/facilities/krec",
    }

    GYM_NAME_MAPPING = {
        "b-fit": "Bruin Fitness Center",
        "wooden": "John Wooden Center",
        "kinross": "Kinross Recreation Center",
    }

    WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    WEEKDAY_NAMES = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1, "tues": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6,
    }

    DINING_URLS = {
        "hours": "https://dining.ucla.edu/hours/",
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
        "bruin-bowl": "https://dining.ucla.edu/bruin-bowl/",
        "trucks": "https://dining.ucla.edu/meal-swipe-exchange/",
    }

    HALL_KEYS = [
        "b-plate", "de-neve", "epic-covel", "epic-ackerman",
        "drey", "study", "rende", "b-cafe", "cafe-1919",
        "feast", "bruin-bowl",
    ]

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
        "Bruin Cafe": "b-cafe",
        "Café 1919": "cafe-1919",
        "Cafe 1919": "cafe-1919",
        "Feast at Rieber": "feast",
        "Spice Kitchen": "feast",
        "Bruin Bowl": "bruin-bowl",
    }

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0"})
        self.current_soup: Optional[BeautifulSoup] = None
        self.dining_data = self._initialize_dining_data()

    def _initialize_dining_data(self) -> Dict[str, Any]:
        """Initialize the main dining data structure."""
        return {
            "halls": {},
            "trucks": {},
            "gyms": {},
            "ASUCLA": {},
            "items": {},
            "last_updated": None,
        }

    @staticmethod
    def _normalize_key(label: str) -> str:
        """Normalize a dynamic meal/column label into a clean lowercase snake_case key."""
        cleaned = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
        if cleaned == "extended_dinner":
            return "ext_dinner"
        return cleaned

    @staticmethod
    def _extract_recipe_id(url: str) -> Optional[str]:
        """Extract recipe ID from ?recipe=<id> query param, falling back to digits."""
        parsed = urlparse(url)
        recipe_vals = parse_qs(parsed.query).get("recipe")
        if recipe_vals and recipe_vals[0].isdigit():
            return recipe_vals[0]
        match = re.search(r"recipe=(\d+)", url)
        if match:
            return match.group(1)
        match = re.search(r"(\d+)", parsed.path)
        return match.group(1) if match else None

    @staticmethod
    def _extract_ajax_params(html_text: str) -> Optional[Dict[str, Any]]:
        """Extract ajaxParams JSON (including activity location_id) from page JS."""
        match = re.search(r"var\s+ajaxParams\s*=\s*(\{.*?\});", html_text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        for b64 in re.findall(r"data:text/javascript;base64,([A-Za-z0-9+/=]+)", html_text):
            try:
                decoded = base64.b64decode(b64).decode("utf-8", errors="ignore")
                match = re.search(r"var\s+ajaxParams\s*=\s*(\{.*?\});", decoded)
                if match:
                    return json.loads(match.group(1))
            except Exception:
                continue
        return None

    # Data Management Methods
    def save_to_local(self, dining_filename: str = DEFAULT_DATA_FILE) -> bool:
        """Save data to JSON files with error handling."""
        try:
            self.dining_data["last_updated"] = datetime.now(PACIFIC_TZ).isoformat()

            with open(dining_filename, "w") as file:
                json.dump(self.dining_data, file, indent=4)

            logger.info(f"Data successfully saved to {dining_filename}")
            return True

        except IOError as e:
            logger.error(f"Error saving data: {e}")
            return False

    def save_to_s3(
        self,
        bucket_name: str = "u-c-lotta-adipose",
        dining_key: str = DEFAULT_DATA_FILE,
        rest_api_id: Optional[str] = None,
        stage_name: Optional[str] = None,
        compress: bool = True,
    ) -> bool:
        """Save data to S3 using boto3 (gzip-compressed by default)."""
        try:
            self.dining_data["last_updated"] = datetime.now(PACIFIC_TZ).isoformat()
            s3_client = boto3.client("s3")

            json_bytes = json.dumps(self.dining_data).encode("utf-8")
            put_kwargs: Dict[str, Any] = {
                "Bucket": bucket_name,
                "Key": dining_key,
                "ContentType": "application/json",
            }
            if compress:
                put_kwargs["Body"] = gzip.compress(json_bytes)
                put_kwargs["ContentEncoding"] = "gzip"
            else:
                put_kwargs["Body"] = json_bytes

            s3_client.put_object(**put_kwargs)

            logger.info(
                f"Data successfully saved to S3: {bucket_name}/{dining_key} "
                f"({len(put_kwargs['Body'])} bytes, gzip={compress})"
            )

            # Clear cache in API Gateway only if API ID & stage are configured
            api_id = rest_api_id or os.environ.get("API_GATEWAY_REST_API_ID", "")
            stage = stage_name or os.environ.get("API_GATEWAY_STAGE_NAME", "")
            if api_id and stage:
                api_client = boto3.client("apigateway")
                api_client.flush_stage_cache(restApiId=api_id, stageName=stage)
                logger.info("API Gateway cache cleared successfully")

            return True

        except Exception as e:
            logger.error(f"Error saving to S3: {e}")
            return False

    def load_from_local(self, dining_filename: str = DEFAULT_DATA_FILE) -> bool:
        """Load from local file; returns False cleanly if the file does not exist yet."""
        if not os.path.exists(dining_filename):
            logger.info(
                f"{dining_filename} does not exist yet; starting with a fresh dataset."
            )
            self.dining_data = self._initialize_dining_data()
            return False

        try:
            with open(dining_filename, "r") as file:
                loaded = json.load(file)
                # Ensure all top-level keys exist even when loading older files
                base = self._initialize_dining_data()
                base.update(loaded)
                self.dining_data = base

        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from local file {dining_filename}: {e}")
            self.dining_data = self._initialize_dining_data()
            return False

        logger.info(f"Data successfully loaded from {dining_filename}")
        return True

    def load_from_s3(
        self,
        bucket_name: str = "u-c-lotta-adipose",
        dining_key: str = DEFAULT_DATA_FILE,
    ) -> bool:
        """Load from S3; initializes a fresh dataset if the object does not exist yet."""
        s3_client = boto3.client("s3")

        try:
            dining_response = s3_client.get_object(Bucket=bucket_name, Key=dining_key)
            raw_bytes = dining_response["Body"].read()
            if raw_bytes[:2] == b"\x1f\x8b":
                raw_bytes = gzip.decompress(raw_bytes)
            loaded = json.loads(raw_bytes.decode("utf-8"))
            base = self._initialize_dining_data()
            base.update(loaded)
            self.dining_data = base

            logger.info(f"Data successfully loaded from S3: {bucket_name}/{dining_key}")
            return True

        except Exception as e:
            logger.info(
                f"Could not load {dining_key} from S3 ({e}); starting with a fresh dataset."
            )
            self.dining_data = self._initialize_dining_data()
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
        return self.dining_data["items"].get(item_id)

    def fetch_nutrition_api(
        self, item_id: str, ingredient_type: str = "recipe", multiplier: float = 1
    ) -> Optional[Dict[str, Any]]:
        """Fetch structured nutrition JSON for a single item from UCLA's nutrition_calc_ajax.php."""
        return self.calculate_meal_nutrition([(item_id, ingredient_type, multiplier)])

    def calculate_meal_nutrition(
        self, items: List[Tuple[str, str, float]]
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate combined nutrition JSON for one or more items via UCLA's nutrition_calc_ajax.php.
        Each entry in `items` is a tuple of (item_id, ingredient_type, multiplier),
        e.g. [('4318', 'recipe', 1), ('2201', 'subrecipe', 2)].
        """
        if not items:
            return None
        try:
            payload = "".join(
                f"{item_id},{ing_type},{mult};" for item_id, ing_type, mult in items
            )
            response = self.session.get(
                self.NUTRITION_CALC_API,
                params={"items": payload},
                timeout=self.timeout,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error calling nutrition API ({items}): {e}")
            return None

    def fetch_activity_level(self, location_id: str) -> Optional[str]:
        """Fetch live activity percentage from UCLA's activity_ajax.php endpoint."""
        try:
            response = self.session.get(
                self.ACTIVITY_API,
                params={"location_id": location_id},
                timeout=self.timeout,
            )
            response.raise_for_status()
            match = re.search(r"(\d+%)", response.text)
            return match.group(1) if match else None
        except Exception as e:
            logger.error(f"Error fetching activity level for location {location_id}: {e}")
            return None

    # Web Scraping Methods
    def _fetch_page(self, url_key: str = "hours") -> bool:
        """Fetch and parse a webpage."""
        try:
            response = self.session.get(self.DINING_URLS[url_key], timeout=self.timeout)
            response.raise_for_status()
            self.current_soup = BeautifulSoup(response.content, "lxml")
            return True
        except requests.RequestException as e:
            logger.error(f"Error fetching page {url_key}: {e}")
            return False

    def scrape_dining_hours(self) -> bool:
        """Scrape dining hall hours for all available days from the /hours/ page."""
        if not self._fetch_page("hours"):
            return False

        try:
            day_panels = self.current_soup.find_all("div", class_="hours-day-panel")
            day_select = self.current_soup.find("select", class_="hours-date-select")

            # Map data-day-index -> 3-letter weekday abbreviation (e.g., "wed")
            index_to_day: Dict[str, str] = {}
            if day_select:
                for opt in day_select.find_all("option"):
                    idx = opt.get("value")
                    label = opt.get_text(" ", strip=True)
                    day_match = re.search(
                        r"\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\b",
                        label,
                        re.IGNORECASE,
                    )
                    if idx is not None and day_match:
                        index_to_day[idx] = day_match.group(1).lower()[:3]

            if day_panels:
                now_pt = datetime.now(PACIFIC_TZ)
                for i, panel in enumerate(day_panels):
                    idx = panel.get("data-day-index", str(i))
                    day_key = index_to_day.get(
                        idx,
                        (now_pt + timedelta(days=i)).strftime("%a").lower(),
                    )
                    table = panel.find("table", class_="dining-hours-table")
                    if table:
                        self._parse_dining_hours_table(table, day_key)
                logger.info("Successfully scraped dining hours for all days")
                return True

            # Fallback: single dining-hours-table
            schedule_table = self.current_soup.find("table", class_="dining-hours-table")
            if not schedule_table:
                logger.error("Could not find dining hours table")
                return False

            current_day = datetime.now(PACIFIC_TZ).strftime("%a").lower()
            self._parse_dining_hours_table(schedule_table, current_day)
            logger.info("Successfully scraped dining hours")
            return True

        except Exception as e:
            logger.error(f"Error parsing dining hours: {e}")
            return False

    def _parse_dining_hours_table(self, table: BeautifulSoup, day: str) -> None:
        """Parse a dining hours table using dynamic column headers from <thead>."""
        header_cells = [th.get_text(" ", strip=True) for th in table.find_all("th")]
        meal_columns = [self._normalize_key(h) for h in header_cells[1:]]

        tbody = table.find("tbody") or table
        for row in tbody.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            loc_cell = cells[0]
            link_tag = loc_cell.find("a", href=True)
            location_name = (
                link_tag.get_text(" ", strip=True)
                if link_tag
                else loc_cell.get_text(" ", strip=True)
            )

            if location_name not in self.LOCATION_NAME_MAPPING:
                continue

            hall_key = self.LOCATION_NAME_MAPPING[location_name]
            location_url = (
                urljoin(self.BASE_URL, link_tag["href"])
                if link_tag
                else self.DINING_URLS.get(hall_key, "")
            )

            if hall_key not in self.dining_data["halls"]:
                self.dining_data["halls"][hall_key] = {
                    "link": location_url,
                    "hours": {},
                }

            day_hours: Dict[str, str] = {}
            for col_idx, cell in enumerate(cells[1:]):
                col_name = (
                    meal_columns[col_idx]
                    if col_idx < len(meal_columns)
                    else f"period_{col_idx + 1}"
                )
                day_hours[col_name] = cell.get_text(" ", strip=True)

            self.dining_data["halls"][hall_key]["hours"][day] = day_hours

    def scrape_food_truck_hours(self) -> bool:
        """Scrape food truck hours and schedules."""
        if not self._fetch_page("trucks"):
            return False

        try:
            self._parse_truck_schedules(self.current_soup)
            logger.info("Successfully scraped food truck hours")
            return True

        except Exception as e:
            logger.error(f"Error scraping food truck hours: {e}")
            return False

    def _parse_truck_schedules(self, soup: BeautifulSoup) -> None:
        """Parse food truck schedules dynamically from table headers and rows."""
        headings = soup.find_all("h3", class_="wp-block-heading")

        for heading in headings:
            location_name = heading.get_text(" ", strip=True).lower()
            table = heading.find_next("table")
            if not table:
                continue

            if location_name not in self.dining_data["trucks"]:
                self.dining_data["trucks"][location_name] = {}

            # Dynamically read time-slot column headers from <thead>
            thead = table.find("thead")
            time_slots = []
            if thead:
                ths = thead.find_all("th")
                time_slots = [th.get_text(" ", strip=True) for th in ths[1:]]

            tbody = table.find("tbody") or table
            for row in tbody.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) < 2:
                    continue

                raw_date_label = " ".join(cells[0].get_text(" ", strip=True).split())
                day_match = re.match(r"([A-Za-z]{3})", raw_date_label)
                day_key = (
                    day_match.group(1).lower()
                    if day_match
                    else raw_date_label.lower()[:3]
                )
                date_match = re.search(r"\[([^\]]+)\]", raw_date_label)
                date_str = date_match.group(1).strip() if date_match else None

                day_schedule: Dict[str, Any] = {}
                if date_str:
                    day_schedule["date"] = date_str

                for idx, cell in enumerate(cells[1:]):
                    slot_name = (
                        time_slots[idx] if idx < len(time_slots) else f"slot_{idx + 1}"
                    )
                    lines = [
                        line.strip()
                        for line in cell.get_text(separator="\n").splitlines()
                        if line.strip()
                    ]
                    if not lines or (len(lines) == 1 and lines[0].upper() == "CLOSED"):
                        day_schedule[slot_name] = []
                    else:
                        day_schedule[slot_name] = lines

                self.dining_data["trucks"][location_name][day_key] = day_schedule

    def scrape_hall_menus(
        self,
        halls: Optional[List[str]] = None,
        dates: Optional[List[str]] = None,
        scrape_items: bool = True,
    ) -> bool:
        """Scrape menus for specified dining halls."""
        if halls is None:
            halls = list(self.HALL_KEYS)

        if dates is None:
            now_pt = datetime.now(PACIFIC_TZ)
            dates = [
                (now_pt + timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(-1, 6)
            ]

        total_attempts = len(halls) * len(dates)
        success_count = 0
        for hall in halls:
            for date in dates:
                if self._scrape_single_hall_menu(hall, date, scrape_items=scrape_items):
                    success_count += 1

        logger.info(
            f"Successfully scraped {success_count}/{total_attempts} hall-date menus"
        )
        return success_count > 0

    def _scrape_single_hall_menu(
        self,
        hall: str,
        date: Optional[str] = None,
        scrape_items: bool = True,
    ) -> bool:
        """Scrape menu for a single dining hall and date."""
        if date is None:
            date = datetime.now(PACIFIC_TZ).strftime("%Y-%m-%d")

        if hall not in self.dining_data["halls"]:
            if hall not in self.DINING_URLS:
                logger.warning(f"Hall {hall} not found in dining URLs")
                return False
            self.dining_data["halls"][hall] = {
                "link": self.DINING_URLS[hall],
                "hours": {},
            }

        hall_url = self.dining_data["halls"][hall]["link"].rstrip("/")

        try:
            response = self.session.get(f"{hall_url}/?date={date}", timeout=self.timeout)
            response.raise_for_status()
            html_text = response.text
            hall_soup = BeautifulSoup(response.content, "lxml")

            # Extract activity location_id from page JS if present
            ajax_params = self._extract_ajax_params(html_text)
            if ajax_params and ajax_params.get("location_id"):
                self.dining_data["halls"][hall]["activity_location_id"] = str(
                    ajax_params["location_id"]
                )

            # Parse today's hours summary from the hall page as well
            self._parse_hall_hours_summary(hall_soup, hall)

            self._parse_hall_menu_sections(
                hall_soup, hall, date, scrape_items=scrape_items
            )
            logger.info(f"Successfully scraped menu for {hall} ({date})")
            return True

        except requests.RequestException as e:
            logger.error(f"Error fetching menu for {hall} ({date}): {e}")
            return False

    def _parse_hall_hours_summary(self, soup: BeautifulSoup, hall: str) -> None:
        """Parse dynamic today's dining hours embedded on an individual hall page."""
        summary = soup.find("div", class_="dining-hours-summary")
        if not summary:
            return
        today_key = datetime.now(PACIFIC_TZ).strftime("%a").lower()
        if today_key in self.dining_data["halls"][hall].get("hours", {}):
            return

        day_hours: Dict[str, str] = {}
        for item in summary.find_all("div", class_="dining-hours-item"):
            name_el = item.find("span", class_="meal-name")
            time_el = item.find("span", class_="meal-time")
            if name_el and time_el:
                day_hours[self._normalize_key(name_el.get_text(strip=True))] = (
                    time_el.get_text(" ", strip=True)
                )

        if day_hours:
            self.dining_data["halls"][hall].setdefault("hours", {})[today_key] = (
                day_hours
            )

    def _parse_hall_menu_sections(
        self,
        soup: BeautifulSoup,
        hall: str,
        day: str,
        scrape_items: bool = True,
    ) -> None:
        """Dynamically parse all meal periods and categories for a dining hall."""
        if "menu" not in self.dining_data["halls"][hall]:
            self.dining_data["halls"][hall]["menu"] = {}

        if day in self.dining_data["halls"][hall]["menu"]:
            logger.info(f"Menu for {hall} on {day} already exists")
            return

        menu_anchors = soup.find_all("div", class_="anchor-float")
        if not menu_anchors:
            closed_today = soup.find("p", class_="dining-status")
            if closed_today:
                logger.info(f"{hall} status on {day}: {closed_today.get_text(strip=True)}")
            self.dining_data["halls"][hall]["menu"][day] = {"open": False}
            return

        self.dining_data["halls"][hall]["menu"][day] = {"open": True}

        for anchor in menu_anchors:
            wrapper = anchor.find_next_sibling("div")
            heading = wrapper.find("h2") if wrapper else anchor.find_next("h2")
            if not heading:
                continue

            meal_type = self._normalize_key(heading.get_text(" ", strip=True))
            if not meal_type:
                continue

            self.dining_data["halls"][hall]["menu"][day][meal_type] = {}

            container = (
                wrapper.find("div", class_="at-a-glance-menu__dining-location")
                if wrapper
                else anchor.find_next("div", class_="at-a-glance-menu__dining-location")
            )
            if container:
                self._parse_menu_container(
                    container, hall, day, meal_type, scrape_items=scrape_items
                )

    def _parse_menu_container(
        self,
        container: BeautifulSoup,
        hall: str,
        day: str,
        meal_type: str,
        scrape_items: bool = True,
    ) -> None:
        """Parse all station/category sections inside a meal period container."""
        stations = container.find_all("div", class_="meal-station")
        if not stations:
            # Fallback for older/alternate markup without meal-station class
            stations = [c for c in container.contents if getattr(c, "name", None) == "div"]

        for station in stations:
            station_header = station.find("h2")
            if not station_header:
                continue

            station_name = " ".join(station_header.get_text(" ", strip=True).split())
            recipe_list = station.find("div", class_="recipe-list")
            if not recipe_list:
                continue

            item_ids: List[str] = []
            for card in recipe_list.find_all("section", class_="recipe-card"):
                link_el = card.find("a", class_="recipe-detail-link", href=True) or card.find(
                    "a", href=True
                )
                if not link_el:
                    continue

                item_link = urljoin(self.BASE_URL, link_el["href"])
                item_id = self._extract_recipe_id(item_link)
                if not item_id:
                    continue

                item_ids.append(item_id)

                card_meta = self._parse_recipe_card_metadata(card)
                if scrape_items:
                    self._scrape_menu_item(item_id, item_link, fallback_meta=card_meta)
                elif item_id not in self.dining_data["items"]:
                    self.dining_data["items"][item_id] = card_meta

            if item_ids:
                self.dining_data["halls"][hall]["menu"][day][meal_type][
                    station_name
                ] = item_ids

    @staticmethod
    def _parse_recipe_card_metadata(card: BeautifulSoup) -> Dict[str, Any]:
        """Extract name, description, dietary icons, and allergen icons from a menu card."""
        meta: Dict[str, Any] = {}
        title_el = card.find("h3")
        if title_el:
            meta["name"] = " ".join(title_el.get_text(" ", strip=True).split())

        desc_el = card.find("p", class_="recipeDescription")
        if desc_el:
            meta["description"] = " ".join(desc_el.get_text(" ", strip=True).split())

        dietary: List[str] = []
        allergens: List[str] = []
        for img in card.find_all("img", class_="menu-meal-station__allergen-icon"):
            label = img.get("title") or img.get("alt") or ""
            label = label.strip()
            if not label:
                continue
            classes = img.get("class", [])
            if "de-diet-icon" in classes:
                dietary.append(label)
            elif "de-allergen-icon" in classes:
                allergens.append(label)
            else:
                dietary.append(label)

        if dietary:
            meta["dietary"] = dietary
        if allergens:
            meta["allergens"] = allergens
        meta["labels"] = dietary + allergens
        return meta

    def _scrape_menu_item(
        self,
        item_id: str,
        url: str,
        fallback_meta: Optional[Dict[str, Any]] = None,
        scrape_subrecipes: bool = True,
    ) -> bool:
        """Scrape nutrition, ingredients, and allergen information for a menu item."""
        if item_id in self.dining_data["items"]:
            logger.debug(f"Item {item_id} already exists")
            return True

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")

            # Custom/build-your-own items now also include an interactive #nutrition calculator
            # alongside .complex-ingredient-group, so detect custom items first.
            if soup.find("div", class_="complex-ingredient-group"):
                return self._scrape_custom_item(
                    item_id,
                    url,
                    soup,
                    fallback_meta=fallback_meta,
                    scrape_subrecipes=scrape_subrecipes,
                )

            item_info = self._parse_standard_item(soup)
            if item_info:
                if fallback_meta:
                    for key in ("description", "dietary"):
                        if key in fallback_meta and key not in item_info:
                            item_info[key] = fallback_meta[key]
                self.dining_data["items"][item_id] = item_info
                return True

            return False

        except Exception as e:
            logger.error(f"Error scraping item {item_id}: {e}")
            return False

    def _parse_standard_item(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parse a standard menu item page with nutrition facts, ingredients, and allergens."""
        try:
            item_info: Dict[str, Any] = {}

            # Item name
            name_element = soup.find("h2", class_="headline-text__lg")
            if not name_element:
                return None
            item_info["name"] = " ".join(name_element.get_text(" ", strip=True).split())

            # Optional description
            desc_element = soup.find("p", class_="single-description")
            if desc_element:
                desc_text = " ".join(desc_element.get_text(" ", strip=True).split())
                if desc_text:
                    item_info["description"] = desc_text

            # Dietary & allergen badges from single-metadata-item-wrapper
            labels: List[str] = []
            wrappers = soup.find_all("div", class_="single-metadata-item-wrapper")
            if wrappers:
                for wrapper in wrappers:
                    img = wrapper.find("img")
                    label = None
                    if img and img.get("src"):
                        match = re.search(r"([^/]+)\.(?:svg|png)", img["src"])
                        if match:
                            label = match.group(1)
                    if not label:
                        label = wrapper.get_text(" ", strip=True)
                    if label:
                        labels.append(label)
            else:
                content_div = soup.find("div", class_="single-menu-page-content")
                if content_div:
                    for icon in content_div.find_all("img"):
                        src = icon.get("src", "")
                        match = re.search(r"([^/]+)\.(?:svg|png)", src)
                        if match:
                            labels.append(match.group(1))
            item_info["labels"] = labels

            # Nutrition facts
            nutrition_section = soup.find("div", id="nutrition")
            if not nutrition_section:
                return None

            # Serving size (scoped inside #nutrition)
            serving_element = nutrition_section.find("strong")
            if serving_element and serving_element.next_sibling:
                serving_text = str(serving_element.next_sibling).strip()
                if serving_text:
                    item_info["serving_size"] = serving_text

            # Calories
            calories_element = nutrition_section.find("p", class_="single-calories")
            if calories_element:
                calories_span = calories_element.find("span")
                if calories_span and calories_span.next_sibling:
                    item_info["calories"] = str(calories_span.next_sibling).strip()

            # Parse both single-column and two-column nutrition tables by (name/val, dv) td pairs
            for table in nutrition_section.find_all("table", class_="nutritive-table"):
                for row in table.find_all("tr"):
                    cells = row.find_all("td")
                    for idx in range(0, len(cells) - 1, 2):
                        nutrient_cell = cells[idx]
                        dv_cell = cells[idx + 1]
                        span = nutrient_cell.find("span")
                        if not span:
                            continue
                        nutrient_name = span.get_text(" ", strip=True).lower()
                        raw_val = (
                            str(span.next_sibling).strip()
                            if span.next_sibling
                            else ""
                        )
                        dv_val = dv_cell.get_text(" ", strip=True).replace("\xa0", "")
                        if nutrient_name and raw_val:
                            item_info[nutrient_name] = [
                                raw_val,
                                dv_val if dv_val else None,
                            ]

            # Ingredients & Allergens tab (#ingredient_list)
            ingredient_section = soup.find("div", id="ingredient_list")
            if ingredient_section:
                ing_items = [
                    " ".join(li.get_text(" ", strip=True).split())
                    for li in ingredient_section.find_all("li")
                    if li.get_text(strip=True)
                ]
                if ing_items:
                    item_info["ingredients"] = ing_items

                for strong in ingredient_section.find_all("strong"):
                    if "allergens" in strong.get_text(strip=True).lower():
                        allergens_text = (
                            str(strong.next_sibling).strip()
                            if strong.next_sibling
                            else ""
                        )
                        if allergens_text:
                            item_info["allergens"] = [
                                a.strip()
                                for a in allergens_text.split(",")
                                if a.strip()
                            ]
                        break

            return item_info

        except Exception as e:
            logger.error(f"Error parsing standard item: {e}")
            return None

    def _scrape_custom_item(
        self,
        item_id: str,
        url: str,
        soup: BeautifulSoup,
        fallback_meta: Optional[Dict[str, Any]] = None,
        scrape_subrecipes: bool = True,
    ) -> bool:
        """Handle custom/complex items with sub-recipe ingredient groups."""
        try:
            item_info: Dict[str, Any] = {"custom": True}

            name_element = soup.find("h2", class_="headline-text__lg")
            if not name_element:
                return False
            item_info["name"] = " ".join(name_element.get_text(" ", strip=True).split())

            desc_element = soup.find("p", class_="single-description")
            if desc_element:
                desc_text = " ".join(desc_element.get_text(" ", strip=True).split())
                if desc_text:
                    item_info["description"] = desc_text
            elif fallback_meta and "description" in fallback_meta:
                item_info["description"] = fallback_meta["description"]

            item_info["ingredients"] = {}
            ingredient_sections = soup.find_all("div", class_="complex-ingredient-group")

            for idx, section in enumerate(ingredient_sections):
                header = section.find(["h4", "h5", "h3"])
                section_label = (
                    header.get_text(" ", strip=True)
                    if header and header.get_text(strip=True)
                    else f"group_{idx + 1}"
                )
                item_info["ingredients"][section_label] = []

                for ingredient in section.find_all("li"):
                    link_element = ingredient.find("a", href=True)
                    if link_element:
                        ingredient_url = urljoin(self.BASE_URL, link_element["href"])
                        ingredient_id = self._extract_recipe_id(ingredient_url)
                        if ingredient_id:
                            item_info["ingredients"][section_label].append(ingredient_id)
                            if scrape_subrecipes:
                                self._scrape_menu_item(ingredient_id, ingredient_url)

            self.dining_data["items"][item_id] = item_info
            return True

        except Exception as e:
            logger.error(f"Error parsing custom item {item_id}: {e}")
            return False

    # Gym Scraping Methods
    def scrape_gym_hours(self, gyms: Optional[List[str]] = None) -> bool:
        """Scrape operating hours, special/holiday hours, and location for UCLA gyms."""
        if gyms is None:
            gyms = list(self.GYM_URLS.keys())

        success_count = 0
        for gym_key in gyms:
            url = self.GYM_URLS.get(gym_key)
            if not url:
                logger.warning(f"Unknown gym key: {gym_key}")
                continue
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "lxml")
                self._parse_gym_page(soup, gym_key, url)
                success_count += 1
                logger.info(f"Successfully scraped gym info for {gym_key}")
            except Exception as e:
                logger.error(f"Error scraping gym {gym_key}: {e}")

        return success_count > 0

    def _expand_day_range(self, day_spec: str) -> List[str]:
        """Expand a day or day range like 'Monday-Thursday' or 'Saturday-Sunday' to ['mon', ...]."""
        cleaned = re.sub(r"[\u200b\u00a0]", "", day_spec).strip().lower()
        parts = re.split(r"\s*[-–—]\s*", cleaned)
        if len(parts) == 1:
            idx = self.WEEKDAY_NAMES.get(parts[0])
            return [self.WEEKDAYS[idx]] if idx is not None else []
        if len(parts) == 2:
            start = self.WEEKDAY_NAMES.get(parts[0])
            end = self.WEEKDAY_NAMES.get(parts[1])
            if start is not None and end is not None:
                if start <= end:
                    return self.WEEKDAYS[start : end + 1]
                return self.WEEKDAYS[start:] + self.WEEKDAYS[: end + 1]
        return []

    def _parse_gym_page(self, soup: BeautifulSoup, gym_key: str, url: str) -> None:
        """Parse regular hours, special/holiday hours, notes, and location from a gym page."""
        gym_info: Dict[str, Any] = {
            "name": self.GYM_NAME_MAPPING.get(gym_key, gym_key),
            "link": url,
            "hours": {},
            "special_hours": {},
            "notes": [],
            "location": "",
        }

        for h2 in soup.find_all("h2"):
            heading_text = re.sub(r"[\u200b\u00a0]", "", h2.get_text(" ", strip=True)).strip()

            if heading_text.lower() == "hours":
                first_hours_block = True
                for sib in h2.find_next_siblings():
                    if sib.name == "h2" or (
                        sib.name == "div" and "ucla-embedded-entity" in (sib.get("class") or [])
                    ):
                        break
                    if sib.name != "p":
                        continue
                    # Skip link-only paragraphs (e.g. Annual Overview Box PDF link)
                    if sib.find("a") and not sib.find("br"):
                        continue

                    lines = [
                        re.sub(r"[\u200b\u00a0]", "", line).strip()
                        for line in sib.get_text(separator="\n").splitlines()
                        if re.sub(r"[\u200b\u00a0]", "", line).strip()
                    ]
                    if not lines:
                        continue

                    strong = sib.find("strong")
                    section_title = (
                        re.sub(r"[\u200b\u00a0]", "", strong.get_text(" ", strip=True))
                        .strip()
                        .rstrip(":")
                        if strong
                        else None
                    )

                    if not strong:
                        gym_info["notes"].extend(lines)
                        continue

                    # Drop the section title line itself from entries
                    entries = [
                        l for l in lines if l.rstrip(":").lower() != (section_title or "").lower()
                    ]

                    if first_hours_block:
                        first_hours_block = False
                        gym_info["hours_label"] = section_title
                        for entry in entries:
                            if ":" in entry:
                                day_part, time_part = entry.split(":", 1)
                                days = self._expand_day_range(day_part)
                                if days:
                                    for d in days:
                                        gym_info["hours"][d] = time_part.strip()
                                    continue
                        if not gym_info["hours"] and entries:
                            gym_info["special_hours"][section_title or "Hours"] = entries
                    else:
                        gym_info["special_hours"][section_title or "Special Hours"] = entries

            elif heading_text.lower() == "location":
                loc_parts: List[str] = []
                for sib in h2.find_next_siblings():
                    if sib.name == "h2" or (
                        sib.name == "div" and "ucla-embedded-entity" in (sib.get("class") or [])
                    ):
                        break
                    if sib.name == "p":
                        lines = [
                            re.sub(r"[\u200b\u00a0]", "", line).strip()
                            for line in sib.get_text(separator="\n").splitlines()
                            if re.sub(r"[\u200b\u00a0]", "", line).strip()
                        ]
                        loc_parts.extend(lines)
                gym_info["location"] = ", ".join(loc_parts)

        self.dining_data.setdefault("gyms", {})[gym_key] = gym_info

    # Main execution methods
    def scrape_all_data(self) -> bool:
        """Scrape all available dining and gym data."""
        logger.info("Starting comprehensive data scraping...")

        success_flags = [
            self.scrape_dining_hours(),
            self.scrape_food_truck_hours(),
            self.scrape_hall_menus(),
            self.scrape_gym_hours(),
        ]

        overall_success = all(success_flags)
        logger.info(f"Data scraping completed. Success: {overall_success}")
        return overall_success

    def update_and_save(
        self,
        use_s3: bool = False,
        dining_filename: str = DEFAULT_DATA_FILE,
        bucket_name: str = "u-c-lotta-adipose",
    ) -> bool:
        """
        Load existing dining-data.json if present (or bootstrap a fresh file on first run),
        scrape all data (hours, food trucks, full menus + items, gym hours), and persist it.
        """
        if use_s3:
            self.load_from_s3(bucket_name=bucket_name, dining_key=dining_filename)
        else:
            self.load_from_local(dining_filename=dining_filename)

        success = self.scrape_all_data()
        if success:
            if use_s3:
                return self.save_to_s3(
                    bucket_name=bucket_name, dining_key=dining_filename
                )
            return self.save_to_local(dining_filename=dining_filename)
        return False


def lambda_handler(event: Optional[Dict[str, Any]] = None, context: Any = None) -> Dict[str, Any]:
    """AWS Lambda entry point for scheduled daily scraping to S3."""
    bucket_name = os.environ.get("S3_BUCKET_NAME", "u-c-lotta-adipose")
    data_key = os.environ.get("S3_DATA_KEY", UCLADiningScraper.DEFAULT_DATA_FILE)

    scraper = UCLADiningScraper()
    ok = scraper.update_and_save(
        use_s3=True,
        bucket_name=bucket_name,
        dining_filename=data_key,
    )
    if not ok:
        raise RuntimeError("Daily UCLA dining scrape failed")

    return {
        "statusCode": 200,
        "bucket": bucket_name,
        "key": data_key,
        "halls": len(scraper.dining_data.get("halls", {})),
        "items": len(scraper.dining_data.get("items", {})),
        "gyms": len(scraper.dining_data.get("gyms", {})),
        "last_updated": scraper.dining_data.get("last_updated"),
    }


# Example usage and API integration
def main():
    """Example usage of the scraper."""
    scraper = UCLADiningScraper()

    if scraper.update_and_save():
        print("Successfully updated and saved dining data")

    return scraper


if __name__ == "__main__":
    main()
