import requests, os, csv, time, re
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from twilio.rest import Client
from typing import List, NewType
from selenium import webdriver

# Load values for the twilio module from the .env file
load_dotenv()
ListOfLists = List[List[str]]


def get_data(url: str) -> BeautifulSoup:
    """Pull data from the  given url and parse it into a soup object.

    Args:
        url (str): url path to the desired page.

    Returns:
        BeautifulSoup: Object containing the parsed html from the page.
    """
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'lxml')
    return soup


def get_positions(url: str, soup) -> ListOfLists:
    """Creates a list of all the desired positions in the BeautifulSoup object through finding links and filtering.

    Args:
        url (str): url path to the desired page. This is need to recreate the entire link.
        soup (BeautifulSoup): Object containing the parsed html.

    Returns:
        ListOfLists: List of lists with all of the selected positions from the parsed data.
    """
    base_url = os.path.dirname(url)
    data = [['position', 'location', 'link']]

    for link in soup.find_all('a'):
        if 'Intern' in link.text:
            info = [link.text, link.parent.span.text, base_url+link['href']]
            for idx, item in enumerate(info):
                info[idx] = item.strip()
            data.append(info)
    return data


def read_csv(file: str) -> ListOfLists:
    """Reads the '.csv' file of the data from the last scrape of the site.

    Args:
        file (str): Name/path of the file to read the data from. Should be a '.csv' file.

    Returns:
        ListOfLists: Reeturns the data as a list of lists with the first being the headers.
    """
    with open(file, 'r') as fin:
        reader = csv.reader(fin, delimiter='\t')
        return list(reader)


def write_csv(file: str, data: ListOfLists, newline='') -> None:
    """Writes the  data to a '.csv' file in order to determine if changes have been made.

    Args:
        file (str): Name/path of the  file to write the data to. Should be  a '.csv' file.
        data (ListOfLists): Data formatted as a list of lists with the first line being the headers.
        newline (str, optional): Prevents confilicts within the Python csv module. Defaults to ''.
    """
    with open(file, 'w') as fout:
        writer = csv.writer(fout, delimiter='\t')
        writer.writerows(data)


def send_text(text: str) -> str:
    """Sends a text message to the defined user (in '.env' file) containing any changes detected.

    Args:
        text (str): Contents of the message.

    Returns:
        str: String identifier of the messaage from the twilio API.
    """
    account_sid = os.getenv('SID')
    auth_token = os.getenv('AUTH')
    client = Client(account_sid, auth_token)

    message = client.messages \
                    .create(
                         body=text,
                         from_=os.getenv('FROM'),
                         to=os.getenv('TO')
                     )

    return(message.sid)


def compare(new: ListOfLists, old: ListOfLists) -> str:
    """Compares the newly scraped data from that of the previous and generates a string containing any detected  changes.

    Args:
        new (ListOfLists): Selected positions from the  scraped data.
        old (ListOfLists): Results of the previous scraped data.

    Returns:
        str: Message  conaaining any updates, formatted to be sent as a text message.
    """
    changes = ['New positions: \n']
    if new == old:
        changes.append('No changes')

    for new_pos in new:
        if new_pos in old:
            continue
        elif new_pos[0] == 'Status:':
            changes.append(' '.join(new_pos))
        else:
            msg = [f'Added: {new_pos[0]}', f'Location: {new_pos[1]}', f'Link: {new_pos[2]}', '\n']
            changes.extend(msg)

    for old_pos in old:
        if old_pos in new:
            continue
        else:
            changes.append(f'Removed: {str(old_pos[0])}')
    return '\n'.join(changes)


def scrape_unops(url: str) -> List[str]:
    """Logs in to the UNOPS application page using credentials defined in a '.env' file. Scrapes the page and returns the status of the application.

    Args:
        url (str): Url path to the UNOPS log in page.

    Returns:
        List[str]: Return the status of the application.
    """
    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")
    options.add_argument("--headless")
    driver = webdriver.Chrome(executable_path='/Users/evan/programming/resources/chromedriver', options=options)

    driver.get(url)
    time.sleep(3)

    username = driver.find_element_by_id("MainPageContent_lgnUser_UserName")
    username.clear()
    user_name = os.getenv('USERNAME')
    username.send_keys(user_name)

    password = driver.find_element_by_id("MainPageContent_lgnUser_Password")
    password.clear()
    pass_word = os.getenv('PASS')
    password.send_keys(pass_word)

    submit = driver.find_element_by_id("MainPageContent_lgnUser_btnLogin")
    submit.click()
    html = driver.page_source
    soup = BeautifulSoup(html, 'lxml')
    data = [re.sub('\W', '', cell.text) for cell in soup.find_all('td', {"class": "p9_status"})]
    data = ['Status:'] + data
    return data


fetch_url = 'https://boards.greenhouse.io/fetchrewards'
unops_url = 'https://jobs.unops.org/Pages/Account/Login.aspx?ReturnUrl=%2fpages%2fuser%2fapplications.aspx'
file = 'last.csv'


html = get_data(fetch_url)
new = get_positions(fetch_url, html)
new.append(scrape_unops(unops_url))
old = read_csv(file)
msg = compare(new, old)
send_text(msg)
write_csv(file, new)
