import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import requests
import csv
from datetime import datetime
from dataclasses import dataclass
from typing import List
import time

@dataclass
class Offer:
    price_after_gc: str
    gift_card: str
    total_price: str
    monthly_price: str
    down_payment: str
    bib_premium: str
    bib_monthly: str
    down_return: str

@dataclass
class Carrier:
    name: str
    link: str
    offers: List[Offer]

@dataclass
class Phone:
    name: str
    carriers: List[Carrier]

class BestBuyScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def scrape(self, xml_file_path: str) -> List[Phone]:
        phones = []

        # Fetch XML file from URL or load from local path
        if xml_file_path.startswith("http://") or xml_file_path.startswith("https://"):
            response = self.session.get(xml_file_path)
            response.raise_for_status()
            xml_content = response.content
            root = ET.fromstring(xml_content)
        else:
            tree = ET.parse(xml_file_path)          
            root = tree.getroot()

        for phone_node in root:
            phone_name = phone_node.tag.replace('_', ' ')
            carriers = []

            for url in phone_node:
                carrier = self.scrape_carrier_data(url.text, url.text, phone_name)
                carriers.append(carrier)

            phones.append(Phone(name=phone_name, carriers=carriers))

        return phones

    def extract_carrier_name(self, url: str) -> str:
        carriers = {
            'telus': 'Telus',
            'koodo': 'Koodo',
            'rogers': 'Rogers',
            'fido': 'Fido',
            'freedom-mobile': 'Freedom Mobile',
            'bell': 'Bell',
            'virgin-plus': 'Virgin Plus'
        }

        for key, value in carriers.items():
            if key in url.lower():
                return value
        return 'Unknown'

    def extract_price(self, soup: BeautifulSoup, selector: str) -> str:
        node = soup.select_one(selector)
        if node:
            text = node.get_text().strip().replace('Best Buy Gift Card', '').replace('$', '').strip()
            return text if text else '0'
        return '0'

    def extract_offer_price(self, soup: BeautifulSoup, offer_type: str) -> tuple[str, str]:
        button = soup.find('button', id=lambda x: x and x.endswith(offer_type))
        if not button:
            return 'N/A', 'N/A'

        pricing_container = button.find('div', class_='pricingContainer_3m_rC')
        if not pricing_container:
            return 'N/A', 'N/A'

        monthly_price_div = pricing_container.find('div', class_='monthlyPrice_35UnX')
        monthly_price = 'N/A'
        if monthly_price_div:
            price_text = monthly_price_div.get_text()
            monthly_price = price_text.split('/mo.')[0].replace('$', '').strip()

        down_payment_div = pricing_container.find('div', class_='downPayment_3g6Nz')
        down_payment = 'N/A'
        if down_payment_div:
            payment_text = down_payment_div.get_text()
            down_payment = payment_text.split('down')[0].replace('$', '').strip()

        return monthly_price, down_payment

    def scrape_carrier_data(self, url: str, link: str, phone_name: str) -> Carrier:
        sku = url.split('/')[-1].split('?')[0]
        updatedUrl = f"https://www.bestbuy.ca/api/cellphones-plans-pricing/sku/{sku}?api-version=2022-05-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=qqpzPnL_WPQXWUV73BbXlPLU0EGP_ZfI0vsIJFccWOE"
        carrier_name = self.extract_carrier_name(url)
        print(f"Started Extracting data for {phone_name} - {carrier_name}")

        max_retries = 3
        attempt = 1
        response_text = None

        while attempt <= max_retries:
            try:
                response = self.session.get(updatedUrl)
                if (response.status_code != 200):
                    print(f"Failed to load data for {phone_name} - {carrier_name}")
                    return Carrier(name=carrier_name, link=link, offers=[])
                response_data = response.json()

                plan_type = response_data[0]['type']
                gift_card = response_data[0]['giftCard']
                monthly_price='N/A'
                down_payment='N/A'
                bib_premium='N/A'
                bib_monthly='N/A'
                down_return='N/A'
                
                # Assuming the first response is always keep it
                if (plan_type == 'keep-it'):
                    monthly_price=response_data[0]['monthly']
                    down_payment=response_data[0]['downPayment']
                    total_price = monthly_price * 24 + down_payment
                    price_after_gc = total_price - gift_card if gift_card else total_price

                if (len(response_data) > 1 and response_data[1]['type'] == 'return-it'):
                    bib_monthly = response_data[1]['monthly']
                    down_return = response_data[1]['residualValue']
                    bib_monthly_price = response_data[1]['monthly']
                    bib_down_payment = response_data[1]['downPayment']
                    
                    bib_premium = (f"{total_price - (float(bib_monthly_price) * 24) - float(bib_down_payment):.2f}"
                                if isinstance(bib_monthly_price, float) else 'N/A')

                    


                offer = Offer(
                    price_after_gc=str(price_after_gc),
                    gift_card=gift_card,
                    total_price=f"{total_price:.2f}",
                    monthly_price=monthly_price,
                    down_payment=down_payment,
                    bib_premium=bib_premium,
                    bib_monthly=bib_monthly,
                    down_return=down_return
                )
                return Carrier(name=carrier_name, link=link, offers=[offer])

            except Exception as e:
                if attempt < max_retries:
                    print(f"Retry {attempt} - Error occurred for {phone_name} - {carrier_name}: {str(e)}")
                    time.sleep(2)
                attempt += 1

        print(f"Failed to load data after {max_retries} attempts for {phone_name} - {carrier_name}")
        if response_text:
            print("womp womp")

        return Carrier(
            name=carrier_name,
            link=link,
            offers=[Offer(
                price_after_gc='N/A',
                gift_card='0',
                total_price='N/A',
                monthly_price='N/A',
                down_payment='N/A',
                bib_premium='N/A',
                bib_monthly='N/A',
                down_return='N/A'
            )]
        )

def write_to_csv(phones: List[Phone], file_path: str):
    headers = [
        'Phone', 'Carrier', 'Price After GC', 'Gift Card Amount', 'Total Price',
        'Monthly Price', 'Downpayment', 'BIB Premium', 'BIB Monthly Price',
        'BIB Downpayment', 'Link'
    ]

    carrier_order = ['Fido', 'Rogers', 'Virgin Plus', 'Bell', 'Koodo', 'Telus', 'Freedom Mobile']

    with open(file_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for phone in phones:
            carrier_map = {carrier.name: carrier for carrier in phone.carriers}

            for carrier_name in carrier_order:
                if carrier_name in carrier_map:
                    carrier = carrier_map[carrier_name]
                    for offer in carrier.offers:
                        writer.writerow([
                            phone.name,
                            carrier.name,
                            offer.price_after_gc,
                            offer.gift_card,
                            offer.total_price,
                            offer.monthly_price,
                            offer.down_payment,
                            offer.bib_premium,
                            offer.bib_monthly,
                            offer.down_return,
                            carrier.link
                        ])
                else:
                    writer.writerow([
                        phone.name,
                        carrier_name,
                        '--', '--', '--', '--', '--', '--', '--', '--', '--'
                    ])

def main():
    scraper = BestBuyScraper()
    xml_path = "./bestbuymobile.xml"
    phones = scraper.scrape(xml_path)

    current_date = datetime.now().strftime("%Y%m%d")
    csv_path = f"bestbuy_{current_date}_mobiles.csv"

    write_to_csv(phones, csv_path)
    print("All data has been written to CSV files.")

if __name__ == "__main__":
    main()
