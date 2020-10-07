import attr
import requests
from bs4 import BeautifulSoup


@attr.s
class UntappdBeerResult:
    beer_id: str = attr.ib()
    name: str = attr.ib()
    brewery: str = attr.ib()
    style: str = attr.ib()
    abv: float = attr.ib()
    ibu: float = attr.ib()
    rating: float = attr.ib()


def get_first_result(query: str) -> UntappdBeerResult:
    """TODO proper interface once we get API access"""
    page = requests.get(
        "https://untappd.com/search",
        params={"q": query},
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:81.0) Gecko/20100101 Firefox/81.0"},
    ).text
    soup = BeautifulSoup(page, "html.parser")
    item = soup.find("div", class_="beer-item")
    return UntappdBeerResult(
        beer_id=item.find("a", class_="label")["href"].rsplit("/", 1)[-1],
        name=item.find("p", class_="name").get_text().strip(),
        brewery=item.find("p", class_="brewery").get_text().strip(),
        style=item.find("p", class_="style").get_text().strip(),
        abv=float(item.find("p", class_="abv").get_text().strip().split("%", 1)[0]),
        ibu=float(item.find("p", class_="ibu").get_text().strip().split(" ", 1)[0].replace("N/A", "nan")),
        rating=float(item.find("div", class_="caps")["data-rating"]),
    )
