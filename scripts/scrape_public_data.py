import urllib.request
import re
import json
import os
import urllib.parse
from html.parser import HTMLParser

# Cities/Municipalities to target
CITIES = [
    "Cebu City", "Lapu-Lapu City", "Mandaue City", "Talisay City", "Consolacion", 
    "Minglanilla", "Cordova", "Carcar City", "Danao City", "Toledo City", 
    "Naga City", "Liloan", "Compostela", "Balamban", "Bogo City"
]

def fetch_html(url):
    """Fetches HTML content from a URL using a standard user agent."""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

UCLM_LOCATION = "University of Cebu - Lapu-Lapu and Mandaue"
UCLM_URL = "https://en.wikipedia.org/wiki/University_of_Cebu"

def build_uclm_student_name_pool():
    """Compiles a synthetic, generic pool of current student first names and last names
    for UCLM to ensure privacy and avoid real-person identification.
    No live student lists or celebrity alumni names are used.
    """
    first_names_male = [
        "Juan Miguel", "Jose Mari", "Mark Gil", "Junjun", "Dexter", "John Paul", "Carlo", "Ramon",
        "Kenneth", "Christian", "Reynaldo", "Alvin", "Michael", "Francis", "Jomar", "Sherwin",
        "Edgardo", "Melvin", "Gerald", "Jerome", "Aldrin", "Alexander", "Arnel", "Bryan",
        "Daniel", "Danilo", "Dennis", "Eduardo", "Eric", "Gary", "Jeffrey", "Jonathan",
        "Julius", "Leo", "Noel", "Patrick", "Romeo"
    ]
    
    first_names_female = [
        "Maria Clara", "Rhea Mae", "Angelica", "Mary Joy", "Kassandra", "Christine", "Sarah", "Jonalyn",
        "Michelle", "Princess", "Cherry", "Gwendolyn", "Irish", "Kimberly", "Lovely", "Rachelle",
        "Shiela", "Analyn", "Glenda", "Jocelyn", "Katrina", "Patricia", "Liezel", "Therese",
        "Aida", "Carmen", "Daisy", "Elena", "Elsa", "Grace", "Irene", "Jane", "Janet",
        "Jenny", "Jessica", "Karen", "Rowena"
    ]
    
    last_names = [
        "Dela Cruz", "Santos", "Buot", "Bacalso", "Fernandez", "Alcantara", "Cabahug", "Ceniza",
        "Abella", "Gomez", "Ramos", "Bontuyan", "Villaver", "Suarez", "Tagalog", "Ondoy",
        "Chan", "Lim", "Go", "Ybañez", "Villamor", "Quisumbing", "Arong", "Ruiz", "Gonzales",
        "Almendras", "Abellanosa", "Aranas", "Abarquez", "Andrade", "Aquino", "Arellano",
        "Bacolod", "Bascon", "Baring"
    ]
    
    return sorted(first_names_male), sorted(first_names_female), sorted(last_names)

class BarangayParser(HTMLParser):
    """A simple HTML Parser to extract barangays and schools from Wikipedia pages."""
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_list = False
        self.in_heading = False
        self.current_heading = ""
        self.temp_text = []
        self.barangays = []
        self.schools = []
        self.collect_text = False

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        
        if tag in ['h2', 'h3', 'h4']:
            self.in_heading = True
            self.temp_text = []
            
        elif tag == 'table':
            self.in_table = True
            
        elif tag in ['ul', 'ol']:
            self.in_list = True
            
        elif tag in ['td', 'li'] or (self.in_table and tag == 'a'):
            self.collect_text = True
            self.temp_text = []

    def handle_data(self, data):
        if self.in_heading:
            self.temp_text.append(data)
        elif self.collect_text:
            self.temp_text.append(data)

    def handle_endtag(self, tag):
        if tag in ['h2', 'h3', 'h4']:
            self.in_heading = False
            self.current_heading = "".join(self.temp_text).strip().lower()
            
        elif tag == 'table':
            self.in_table = False
            
        elif tag in ['ul', 'ol']:
            self.in_list = False
            
        elif tag in ['td', 'li'] or tag == 'a':
            self.collect_text = False
            text_val = "".join(self.temp_text).strip()
            text_val = re.sub(r'\[\d+\]', '', text_val).strip()
            
            if text_val:
                # Strictly allow only valid names (letters, spaces, dots, hyphens, and ntilde)
                if re.match(r'^[A-Za-z\s\.\-\ñ\Ñ]+$', text_val):
                    lower_val = text_val.lower()
                    # 1. Collect barangays if under barangay heading
                    if 'barangay' in self.current_heading or 'subdivision' in self.current_heading:
                        if len(text_val) > 2 and len(text_val) < 40:
                            if not any(kw in lower_val for kw in ['total', 'barangay', 'name', 'population', 'area', 'class', 'urban', 'density', 'index', 'province', 'island', 'growth', 'households', 'coordinates', 'coordinate']):
                                clean_name = text_val.split('\n')[0].strip()
                                if clean_name and len(clean_name) > 2:
                                    self.barangays.append(clean_name)
                                    
                    # 2. Collect schools under education heading
                    if 'education' in self.current_heading or 'school' in self.current_heading or 'college' in self.current_heading:
                        if any(kw in lower_val for kw in ["university", "college", "school", "institutes"]):
                            name = text_val.split('-')[0].split('–')[0].split('(')[0].strip()
                            if len(name) > 5 and len(name) < 80 and name not in self.schools:
                                self.schools.append(name)

def scrape_wikipedia_data(city):
    """Queries Wikipedia for a given city and parses geographic reference data."""
    formatted_city = city.replace(" ", "_")
    if city in ["Consolacion", "Minglanilla", "Cordova", "Liloan", "Compostela", "Balamban"]:
        url = f"https://en.wikipedia.org/wiki/{formatted_city},_Cebu"
    elif city in ["Mandaue City"]:
        url = "https://en.wikipedia.org/wiki/Mandaue"
    else:
        url = f"https://en.wikipedia.org/wiki/{formatted_city}"
        
    print(f"Scraping Wikipedia for {city}: {url}")
    html = fetch_html(url)
    if not html:
        return [], []
        
    parser = BarangayParser()
    parser.feed(html)
    
    # Clean and deduplicate lists
    barangays = sorted(list(set([b for b in parser.barangays if len(b) > 2])))
    schools = sorted(list(set([s for s in parser.schools if len(s) > 5])))
    
    print(f"Found {len(barangays)} barangays and {len(schools)} schools for {city}")
    return barangays, schools

def main():
    print("=== Starting Public Cebu Data Scraper (No Dependencies) ===")
    
    # Load base locations file
    locations_file = os.path.join(os.path.dirname(__file__), "..", "data", "cebu_locations.json")
    if os.path.exists(locations_file):
        with open(locations_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
        
    for city in CITIES:
        brgys, schools = scrape_wikipedia_data(city)
        
        # Merge scraped data
        if city not in data:
            data[city] = {"province": "Cebu"}
            
        if brgys:
            data[city]["sample_barangays"] = brgys
        else:
            # Keep existing barangays as fallback
            if "sample_barangays" not in data[city]:
                data[city]["sample_barangays"] = ["Poblacion", "Centro"]
                
        if schools:
            # Merge with existing manually added schools
            existing_schools = data[city].get("sample_schools", [])
            data[city]["sample_schools"] = sorted(list(set(existing_schools + schools)))
        else:
            if "sample_schools" not in data[city]:
                data[city]["sample_schools"] = [f"{city} High School"]
                
        data[city]["sample_address_format"] = f"{{barangay}}, {city}, Cebu"
            
    # Merge UCLM location entry
    uclm_male, uclm_female, uclm_last = build_uclm_student_name_pool()
    if UCLM_LOCATION not in data:
        data[UCLM_LOCATION] = {
            "province": "Cebu",
            "sample_barangays": [
                # Mandaue City (campus area + most populated)
                "Looc, Mandaue City", "Subangdaku, Mandaue City", "Basak, Mandaue City",
                "Cabancalan, Mandaue City", "Centro, Mandaue City", "Banilad, Mandaue City",
                "Maguikay, Mandaue City", "Tipolo, Mandaue City", "Cubacub, Mandaue City",
                "Casuntingan, Mandaue City", "Canduman, Mandaue City", "Paknaan, Mandaue City",
                # Cebu City (most populated)
                "Mabolo, Cebu City", "Lahug, Cebu City", "Guadalupe, Cebu City",
                "Talamban, Cebu City", "Banilad, Cebu City", "Apas, Cebu City",
                "Labangon, Cebu City", "Pardo, Cebu City", "Tisa, Cebu City",
                # Lapu-Lapu City (most populated)
                "Basak, Lapu-Lapu City", "Mactan, Lapu-Lapu City", "Pajo, Lapu-Lapu City",
                "Pusok, Lapu-Lapu City", "Gun-ob, Lapu-Lapu City", "Bankal, Lapu-Lapu City",
                # Consolacion (most populated)
                "Cansaga, Consolacion", "Lamac, Consolacion", "Nangka, Consolacion",
                "Jugan, Consolacion", "Pitogo, Consolacion",
                # Liloan (most populated)
                "Poblacion, Liloan", "Catarman, Liloan", "Yati, Liloan",
                "Cotcot, Liloan", "Calero, Liloan",
            ],
            "sample_schools": ["University of Cebu - Lapu-Lapu and Mandaue"],
            "sample_address_format": "{barangay}, Cebu"
        }
    data[UCLM_LOCATION]["student_first_names_male"] = uclm_male
    data[UCLM_LOCATION]["student_first_names_female"] = uclm_female
    data[UCLM_LOCATION]["student_last_names"] = uclm_last

    # Save the expanded dataset
    os.makedirs(os.path.dirname(locations_file), exist_ok=True)
    with open(locations_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        
    print(f"=== Successfully updated {locations_file} with public scraped data! ===")

if __name__ == "__main__":
    main()
