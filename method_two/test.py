import cfscrape

scraper = cfscrape.create_scraper()  # returns a CloudflareScraper instance
# Or: scraper = cfscrape.CloudflareScraper()  # CloudflareScraper inherits from requests.Session
url = "https://www.caworkcompcoverage.com/Search"
print(scraper.get(url).content)
