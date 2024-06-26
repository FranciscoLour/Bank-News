import streamlit as st
import pandas as pd
import feedparser
from bs4 import BeautifulSoup
import urllib
from dateparser import parse as parse_date
import requests

class GoogleNews:
    def __init__(self, lang='en', country='US'):
        self.lang = lang.lower()
        self.country = country.upper()
        self.BASE_URL = 'https://news.google.com/rss'

    def __top_news_parser(self, text):
        """Return subarticles from the main and topic feeds"""
        try:
            bs4_html = BeautifulSoup(text, "html.parser")
            lis = bs4_html.find_all('li')
            sub_articles = []
            for li in lis:
                try:
                    sub_articles.append({"url": li.a['href'],
                                         "title": li.a.text,
                                         "publisher": li.font.text})
                except:
                    pass
            return sub_articles
        except:
            return text

    def __ceid(self):
        """Compile correct country-lang parameters for Google News RSS URL"""
        return '?ceid={}:{}&hl={}&gl={}'.format(self.country, self.lang, self.lang, self.country)

    def __add_sub_articles(self, entries):
        for i, val in enumerate(entries):
            if 'summary' in entries[i].keys():
                entries[i]['sub_articles'] = self.__top_news_parser(entries[i]['summary'])
            else:
                entries[i]['sub_articles'] = None
        return entries

    def __scaping_bee_request(self, api_key, url):
        response = requests.get(
            url="https://app.scrapingbee.com/api/v1/",
            params={
                "api_key": api_key,
                "url": url,
                "render_js": "false"
            }
        )
        if response.status_code == 200:
            return response
        if response.status_code != 200:
            raise Exception("ScrapingBee status_code: " + str(response.status_code) + " " + response.text)

    def __parse_feed(self, feed_url, proxies=None, scraping_bee=None):

        if scraping_bee and proxies:
            raise Exception("Pick either ScrapingBee or proxies. Not both!")

        if proxies:
            r = requests.get(feed_url, proxies=proxies)
        else:
            r = requests.get(feed_url)

        if scraping_bee:
            r = self.__scaping_bee_request(url=feed_url, api_key=scraping_bee)
        else:
            r = requests.get(feed_url)

        if 'https://news.google.com/rss/unsupported' in r.url:
            raise Exception('This feed is not available')

        d = feedparser.parse(r.text)

        if not scraping_bee and not proxies and len(d['entries']) == 0:
            d = feedparser.parse(feed_url)

        return dict((k, d[k]) for k in ('feed', 'entries'))

    def __search_helper(self, query):
        return urllib.parse.quote_plus(query)

    def __from_to_helper(self, validate=None):
        try:
            validate = parse_date(validate).strftime('%Y-%m-%d')
            return str(validate)
        except:
            raise Exception('Could not parse your date')

    def top_news(self, proxies=None, scraping_bee=None):
        """Return a list of all articles from the main page of Google News
        given a country and a language"""
        d = self.__parse_feed(self.BASE_URL + self.__ceid(), proxies=proxies, scraping_bee=scraping_bee)
        d['entries'] = self.__add_sub_articles(d['entries'])
        return d

    def topic_headlines(self, topic: str, proxies=None, scraping_bee=None):
        """Return a list of all articles from the topic page of Google News
        given a country and a language"""
        if topic.upper() in ['WORLD', 'NATION', 'BUSINESS', 'TECHNOLOGY', 'ENTERTAINMENT', 'SCIENCE', 'SPORTS', 'HEALTH']:
            d = self.__parse_feed(self.BASE_URL + '/headlines/section/topic/{}'.format(topic.upper()) + self.__ceid(), proxies=proxies, scraping_bee=scraping_bee)
        else:
            d = self.__parse_feed(self.BASE_URL + '/topics/{}'.format(topic) + self.__ceid(), proxies=proxies, scraping_bee=scraping_bee)
        d['entries'] = self.__add_sub_articles(d['entries'])
        if len(d['entries']) > 0:
            return d
        else:
            raise Exception('unsupported topic')

    def geo_headlines(self, geo: str, proxies=None, scraping_bee=None):
        """Return a list of all articles about a specific geolocation
        given a country and a language"""
        d = self.__parse_feed(self.BASE_URL + '/headlines/section/geo/{}'.format(geo) + self.__ceid(), proxies=proxies, scraping_bee=scraping_bee)
        d['entries'] = self.__add_sub_articles(d['entries'])
        return d

    def search(self, query: str, helper=True, when=None, from_=None, to_=None, proxies=None, scraping_bee=None):
        """
        Return a list of all articles given a full-text search parameter,
        a country and a language

        :param bool helper: When True helps with URL quoting
        :param str when: Sets a time range for the artiles that can be found
        """
        if when:
            query += ' when:' + when

        if from_ and not when:
            from_ = self.__from_to_helper(validate=from_)
            query += ' after:' + from_

        if to_ and not when:
            to_ = self.__from_to_helper(validate=to_)
            query += ' before:' + to_

        if helper:
            query = self.__search_helper(query)

        search_ceid = self.__ceid()
        search_ceid = search_ceid.replace('?', '&')

        d = self.__parse_feed(self.BASE_URL + '/search?q={}'.format(query) + search_ceid, proxies=proxies, scraping_bee=scraping_bee)

        d['entries'] = self.__add_sub_articles(d['entries'])
        return d


import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

# Function to get news from Google News
def get_news(instituicoes, start_date, end_date):
    gn = GoogleNews(lang="pt", country="PT")
    article_data = []
    for instituicao in instituicoes:
        search_results = gn.search(str(instituicao))
        sorted_articles = sorted(search_results['entries'], key=lambda x: x['published'], reverse=True)
        for entry in sorted_articles:
            publication_date = pd.to_datetime(entry['published'], infer_datetime_format=True).date()
            if start_date <= publication_date <= end_date:
                article_data.append({
                    "Nome Instituiçao": instituicao,
                    "Title": entry['title'],
                    "Link": entry['link'],
                    "Publication Date": publication_date,
                    "Source": entry["source"]["title"]
                })
    df = pd.DataFrame(article_data)
    sorted_df = df.sort_values(by="Publication Date", ascending=False)
    sorted_df.reset_index(inplace=True, drop=True)
    aux = list((sorted_df["Source"].value_counts().index[sorted_df["Source"].value_counts() < 5].tolist()))
    filtered_df = sorted_df[~sorted_df["Source"].isin(["Prefeitura de Ituporanga", "PREFEITURA MUNICIPAL DE VIANA - ES", "mediotejo.net", "Folha de S.Paulo"] + aux)]
    return filtered_df

# Streamlit App
st.sidebar.title("Institution Selection")
institutions = [
    "CGD", "Banco Santander Totta", "Novo Banco", "BCP", "BPI", 
    "BAI Europa", "Banco Atlantico Europa", "BNI Europa", 
    "Banco Montepio", "Banco Carregosa", "Banco Invest", "Banco CTT", "CCAM"
]
selected_institutions = st.sidebar.multiselect("Select Institutions", institutions, default=["CGD","BCP", "Novo Banco", "Banco Santander Totta", "Banco Montepio"])

# Sidebar for date selection
# Sidebar for date selection
st.sidebar.title("Date Selection")
today = date.today()
start_date_default = today - timedelta(days=14)
start_date = st.sidebar.date_input("Start Date", value=start_date_default)
end_date = st.sidebar.date_input("End Date", value=today)

# Preload news results on app load
news_df = get_news(selected_institutions, start_date, end_date)

# Main content
st.title("Google News Dashboard")

if st.sidebar.button("Fetch News"):
    with st.spinner('Retrieving latest news...'):
        news_df = get_news(selected_institutions, start_date, end_date)
        st.success('News retrieved successfully!')

st.write("### News Articles")
for _, row in news_df.iterrows():
    st.markdown(f"#### {row['Title']}")
    st.markdown(f"**Institution:** {row['Nome Instituiçao']}")
    st.markdown(f"**Source:** {row['Source']}")
    st.markdown(f"**Publication Date:** {row['Publication Date'].strftime('%Y-%m-%d')}")
    st.markdown(f"[Read more]({row['Link']})")
    st.markdown("---")