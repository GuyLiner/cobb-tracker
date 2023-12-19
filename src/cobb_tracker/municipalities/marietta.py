import requests
import pathlib
import re
import os
from cobb_tracker.municipalities import file_ops
from cobb_tracker.cobb_config import cobb_config

from bs4.element import Tag
from bs4 import BeautifulSoup

URL_BASE = "https://www.mariettaga.gov"
URL_AGENDAS = f"{URL_BASE}/AgendaCenter"
URL_UPDATE_AGENDAS = f"{URL_BASE}/AgendaCenter/UpdateCategoryList"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0"
)

RE_ALPHNUM = re.compile(r"[^a-zA-Z0-9]")
RE_ALPHA = re.compile(r"[0-9\.\-]")

def process_row_documents(row: Tag,
                          session: requests.Session,
                          container_name: str,
                          config: cobb_config,
                          minutes_url: str) -> None:
    """Parse meeting information and documents from a table row.

    Args:
        row (Tag): Row from a Marietta meeting list table.
        session (requests.Session): Session object for doing HTTP calls.
    """
    meeting_title = row.find("a", {"aria-describedby": True}, target="_blank")
    if meeting_title is None:
        return
    meeting_name = clean_name(meeting_title.text.strip().title())

    date_header = row.find("td", class_=None)

    minutes_name = minutes_url.split("/")[-1]

    doc_id = minutes_name.split("-")[1]
    year = minutes_name[5:9]
    month = minutes_name[1:3]
    day = minutes_name[3:5]

    date=f"{year}-{month}-{day}"
    new_name = f"{date}-minutes-{doc_id}.pdf"

    file_ops.write_minutes_doc(
            doc_date=date,
            session=session,
            meeting_type=meeting_name,
            user_agent=USER_AGENT,
            file_url=minutes_url,
            municipality="Marietta",
            file_type="minutes",
            config=config
            )

def get_years(agenda_container: Tag) -> list[str]:
    """Find all the list items that define which years are available to filter on.

    Args:
        agenda_container (Tag): HTML DOM object that contains the year list.

    Returns:
        list[str]: List of year strings.
    """
    year_list = agenda_container.find("ul", class_="years")
    filtered_year_list = []
    for entry in year_list.find_all("li"):
        entry_string = entry.find("a").text
        if is_year(entry_string):
            filtered_year_list.append(entry_string)
    return filtered_year_list

def get_minutes_docs(config: cobb_config):
    minutes_urls = {}
    session = requests.Session()

    response = session.get(URL_AGENDAS, headers={"User-Agent": USER_AGENT})
    if not response.ok:
        print("Request failed:", response.reason, response.status_code)
        return

    soup = BeautifulSoup(response.content, "html.parser")
    agenda_containers = soup.find_all("div", class_="listing listingCollapse noHeader")
    for container in agenda_containers:
        year_list = get_years(container)
        container_name = (container.find("h2", tabindex="0").text).replace(' ','_')[1:]
        agenda_table_id = re.sub(
            r"[a-zA-Z]",
            "",
            container.find("table", summary="List of Agendas").get("id"),
        )

        for year in year_list:
            payload = {"year": year, "catID": agenda_table_id}
            agendas = session.post(
                URL_UPDATE_AGENDAS, headers={"User-Agent": USER_AGENT}, data=payload
            )
            new_doc = BeautifulSoup(agendas.text, "html.parser")
            rows = new_doc.find_all("tr", class_="catAgendaRow")
            for row in rows:
                minutes = row.find("td", class_="minutes")
                minutes_link = minutes.find("a")
                if minutes_link:
                    minutes_url = f"{URL_BASE}{minutes_link.get('href')}"
                    minutes_urls[minutes_url] = row

    for url in minutes_urls.keys():
        row = minutes_urls[url]
        process_row_documents(
                row=row,
                session=session,
                container_name=container_name,
                config=config,
                minutes_url=url)

def clean_name(input_string: str) -> str:
    """Use regex to replace non-alphanumeric characters with underscores

    Args:
        input_string (str): String to clean and format, such as a meeting title._

    Returns:
        str: Formatted string.
    """
    # TODO: This is a little messy and leaves some errant "_" at the end of some folders.
    input_string = RE_ALPHA.sub("", input_string)
    result_string = (
        RE_ALPHNUM.sub("_", input_string).replace("__", "_").replace("__", "_")
    )
    return result_string


def is_year(input_string: str) -> bool:
    """Is the input string a 4-digit number?

    Args:
        input_string (str): String to evaluate

    Returns:
        bool: Well is it?
    """
    year = re.compile(r"\d{4}")
    return True if year.match(input_string) else False
